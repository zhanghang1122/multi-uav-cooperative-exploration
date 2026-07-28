#!/usr/bin/env python3
"""Record time-resolved evidence required by the paper protocol."""

import csv
import json
import math
import os
import re
import time

import rospy
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from rosgraph_msgs.msg import Log
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2


TIMING_PATTERNS = (
    ("cost_matrix", re.compile(r"Cost mat:\s*([0-9.eE+-]+)")),
    ("tsp", re.compile(r"TSP:\s*([0-9.eE+-]+)")),
    ("local_refine", re.compile(r"Local refine time:\s*([0-9.eE+-]+)")),
    ("trajectory", re.compile(r"Traj:\s*([0-9.eE+-]+)")),
    ("yaw", re.compile(r"yaw:\s*([0-9.eE+-]+)")),
    ("planning_total", re.compile(r"Total time:\s*([0-9.eE+-]+)")),
)
NEXT_VIEW_PATTERN = re.compile(
    r"Next view:\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+"
    r"([0-9.eE+-]+),\s*([0-9.eE+-]+)"
)


class PaperEvidenceRecorder:
    def __init__(self):
        self.start_time = time.monotonic()
        self.duration_s = float(rospy.get_param("~duration_s", 1800.0))
        self.evidence_dir = os.path.abspath(
            rospy.get_param("~evidence_dir", "/tmp/ruins_fuel_base_evidence")
        )
        self.pose_period_s = float(rospy.get_param("~pose_sample_period_s", 0.1))
        self.map_period_s = float(
            rospy.get_param("~occupancy_sample_period_s", 2.0)
        )
        self.resource_period_s = float(
            rospy.get_param("~resource_sample_period_s", 1.0)
        )
        self.resolution_m = float(
            rospy.get_param("~evidence_resolution_m", 0.1)
        )
        self.finish_text = rospy.get_param(
            "~finish_log_text", "finish exploration."
        )
        self.topics = {
            "odometry": rospy.get_param("~odom_topic", "/state_ukf/odom"),
            "occupancy": rospy.get_param(
                "~occupancy_topic", "/sdf_map/occupancy_all"
            ),
            "clock": rospy.get_param("~clock_topic", "/clock"),
            "rosout": "/rosout_agg",
        }
        if min(
            self.pose_period_s,
            self.map_period_s,
            self.resource_period_s,
            self.resolution_m,
        ) <= 0.0:
            raise ValueError("evidence sampling periods and resolution must be positive")

        os.makedirs(self.evidence_dir, exist_ok=True)
        self.closed = False
        self.finished = False
        self.latest_occupancy = None
        self.latest_clock_s = None
        self.first_clock_s = None
        self.previous_cpu_sample = None
        self.last_pose_s = -math.inf
        self.last_map_s = -math.inf
        self.last_resource_s = -math.inf
        self.first_seen_voxels = {}
        self._open_outputs()
        self._write_manifest()
        rospy.on_shutdown(self.close)
        self.subscribers = (
            rospy.Subscriber(
                self.topics["odometry"],
                Odometry,
                self.odometry_callback,
                queue_size=50,
            ),
            rospy.Subscriber(
                self.topics["occupancy"],
                PointCloud2,
                self.occupancy_callback,
                queue_size=2,
            ),
            rospy.Subscriber(
                self.topics["clock"],
                Clock,
                self.clock_callback,
                queue_size=20,
            ),
            rospy.Subscriber(
                self.topics["rosout"],
                Log,
                self.log_callback,
                queue_size=200,
            ),
        )

    def elapsed(self):
        return time.monotonic() - self.start_time

    def _open_csv(self, filename, fields):
        path = os.path.join(self.evidence_dir, filename)
        stream = open(path, "w", encoding="utf-8", newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        return path, stream, writer

    def _open_outputs(self):
        (
            self.trajectory_path,
            self.trajectory_stream,
            self.trajectory_writer,
        ) = self._open_csv(
            "trajectory.csv",
            (
                "elapsed_s",
                "ros_time_s",
                "x_m",
                "y_m",
                "z_m",
                "qx",
                "qy",
                "qz",
                "qw",
                "vx_mps",
                "vy_mps",
                "vz_mps",
            ),
        )
        (
            self.map_growth_path,
            self.map_growth_stream,
            self.map_growth_writer,
        ) = self._open_csv(
            "map_growth_timeseries.csv",
            ("elapsed_s", "raw_points", "occupied_voxels", "new_voxels"),
        )
        (
            self.planning_path,
            self.planning_stream,
            self.planning_writer,
        ) = self._open_csv(
            "planning_timing.csv",
            ("elapsed_s", "module", "duration_s", "source_node"),
        )
        (
            self.resources_path,
            self.resources_stream,
            self.resources_writer,
        ) = self._open_csv(
            "system_resources.csv",
            (
                "elapsed_wall_s",
                "elapsed_sim_s",
                "realtime_factor",
                "load_1m",
                "system_cpu_percent",
                "memory_available_mb",
                "ros_process_rss_mb",
                "recorder_rss_mb",
            ),
        )
        self.events_path = os.path.join(self.evidence_dir, "events.jsonl")
        self.events_stream = open(
            self.events_path, "w", encoding="utf-8", newline="\n"
        )
        self.planner_rosout_path = os.path.join(
            self.evidence_dir, "planner_rosout.jsonl"
        )
        self.planner_rosout_stream = open(
            self.planner_rosout_path, "w", encoding="utf-8", newline="\n"
        )

    def _write_manifest(self):
        payload = {
            "schema_version": 1,
            "protocol_version": rospy.get_param(
                "~protocol_version", "0.1-draft"
            ),
            "run_class": rospy.get_param("~run_class", "debug"),
            "method_id": rospy.get_param("~method_id", "B1_single_fuel"),
            "scene_profile": rospy.get_param("~scene_profile", "base"),
            "scene_seed": rospy.get_param("~scene_seed", "fixed"),
            "repetition": int(rospy.get_param("~repetition", 0)),
            "truth_map_usage": "offline_evaluation_only",
            "prior_route_allowed": False,
            "duration_limit_s": self.duration_s,
            "topics": self.topics,
            "sampling": {
                "pose_period_s": self.pose_period_s,
                "occupancy_period_s": self.map_period_s,
                "resource_period_s": self.resource_period_s,
                "voxel_resolution_m": self.resolution_m,
            },
        }
        path = os.path.join(self.evidence_dir, "run_manifest.yaml")
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def odometry_callback(self, message):
        elapsed = self.elapsed()
        if elapsed - self.last_pose_s < self.pose_period_s:
            return
        position = message.pose.pose.position
        orientation = message.pose.pose.orientation
        velocity = message.twist.twist.linear
        self.trajectory_writer.writerow(
            {
                "elapsed_s": f"{elapsed:.6f}",
                "ros_time_s": f"{message.header.stamp.to_sec():.9f}",
                "x_m": f"{position.x:.6f}",
                "y_m": f"{position.y:.6f}",
                "z_m": f"{position.z:.6f}",
                "qx": f"{orientation.x:.9f}",
                "qy": f"{orientation.y:.9f}",
                "qz": f"{orientation.z:.9f}",
                "qw": f"{orientation.w:.9f}",
                "vx_mps": f"{velocity.x:.6f}",
                "vy_mps": f"{velocity.y:.6f}",
                "vz_mps": f"{velocity.z:.6f}",
            }
        )
        self.trajectory_stream.flush()
        self.last_pose_s = elapsed

    def occupancy_callback(self, message):
        self.latest_occupancy = message

    def clock_callback(self, message):
        self.latest_clock_s = message.clock.to_sec()
        if self.first_clock_s is None:
            self.first_clock_s = self.latest_clock_s

    def write_event(self, event, message, node, values=None):
        payload = {
            "elapsed_s": round(self.elapsed(), 6),
            "event": event,
            "source_node": node,
            "message": message,
        }
        if values is not None:
            payload["values"] = values
        self.events_stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self.events_stream.flush()

    def log_callback(self, message):
        if "exploration_node" not in message.name:
            return
        self.planner_rosout_stream.write(
            json.dumps(
                {
                    "elapsed_s": round(self.elapsed(), 6),
                    "level": message.level,
                    "source_node": message.name,
                    "message": message.msg,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.planner_rosout_stream.flush()
        lower = message.msg.lower()
        if self.finish_text in message.msg:
            self.finished = True
            self.write_event("exploration_finished", message.msg, message.name)
        if "plan fail" in lower:
            self.write_event("planning_failed", message.msg, message.name)
        if "collision detected" in lower:
            self.write_event("collision_replan", message.msg, message.name)
        if "replan:" in lower:
            self.write_event("replan", message.msg, message.name)

        next_view = NEXT_VIEW_PATTERN.search(message.msg)
        if next_view:
            self.write_event(
                "target_view_selected",
                message.msg,
                message.name,
                {
                    "x_m": float(next_view.group(1)),
                    "y_m": float(next_view.group(2)),
                    "z_m": float(next_view.group(3)),
                    "yaw_rad": float(next_view.group(4)),
                },
            )

        wrote_timing = False
        for module, pattern in TIMING_PATTERNS:
            match = pattern.search(message.msg)
            if not match:
                continue
            duration = float(match.group(1))
            if duration >= 0.0 and math.isfinite(duration):
                self.planning_writer.writerow(
                    {
                        "elapsed_s": f"{self.elapsed():.6f}",
                        "module": module,
                        "duration_s": f"{duration:.9f}",
                        "source_node": message.name,
                    }
                )
                wrote_timing = True
        if wrote_timing:
            self.planning_stream.flush()

    def sample_map(self):
        elapsed = self.elapsed()
        if (
            self.latest_occupancy is None
            or elapsed - self.last_map_s < self.map_period_s
        ):
            return
        current = set()
        for x_value, y_value, z_value in point_cloud2.read_points(
            self.latest_occupancy,
            field_names=("x", "y", "z"),
            skip_nans=True,
        ):
            current.add(
                (
                    int(round(x_value / self.resolution_m)),
                    int(round(y_value / self.resolution_m)),
                    int(round(z_value / self.resolution_m)),
                )
            )
        new_voxels = current.difference(self.first_seen_voxels)
        for voxel in new_voxels:
            self.first_seen_voxels[voxel] = elapsed
        self.map_growth_writer.writerow(
            {
                "elapsed_s": f"{elapsed:.6f}",
                "raw_points": (
                    self.latest_occupancy.width * self.latest_occupancy.height
                ),
                "occupied_voxels": len(self.first_seen_voxels),
                "new_voxels": len(new_voxels),
            }
        )
        self.map_growth_stream.flush()
        self.last_map_s = elapsed

    @staticmethod
    def memory_available_mb():
        try:
            with open("/proc/meminfo", "r", encoding="ascii") as stream:
                for line in stream:
                    if line.startswith("MemAvailable:"):
                        return float(line.split()[1]) / 1024.0
        except OSError:
            pass
        return None

    @staticmethod
    def recorder_rss_mb():
        try:
            with open("/proc/self/statm", "r", encoding="ascii") as stream:
                resident_pages = int(stream.read().split()[1])
            return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024.0**2)
        except (OSError, ValueError, IndexError):
            return None

    def system_cpu_percent(self):
        try:
            with open("/proc/stat", "r", encoding="ascii") as stream:
                values = [int(value) for value in stream.readline().split()[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
        except (OSError, ValueError, IndexError):
            return None
        current = (total, idle)
        previous = self.previous_cpu_sample
        self.previous_cpu_sample = current
        if previous is None:
            return None
        total_delta = total - previous[0]
        idle_delta = idle - previous[1]
        if total_delta <= 0:
            return None
        return 100.0 * (1.0 - idle_delta / total_delta)

    @staticmethod
    def ros_process_rss_mb():
        markers = (
            b"/opt/ros/",
            b"/fuel_ws/",
            b"/marsim_ws/",
            b"/catkin_ws/",
            b"roslaunch",
            b"rosmaster",
            b"roscore",
        )
        total_kb = 0
        try:
            process_directories = [
                entry
                for entry in os.scandir("/proc")
                if entry.name.isdigit() and entry.is_dir(follow_symlinks=False)
            ]
        except OSError:
            return None
        for entry in process_directories:
            try:
                with open(
                    os.path.join(entry.path, "cmdline"), "rb"
                ) as command_stream:
                    command = command_stream.read()
                if not any(marker in command for marker in markers):
                    continue
                with open(
                    os.path.join(entry.path, "status"),
                    "r",
                    encoding="ascii",
                    errors="ignore",
                ) as status_stream:
                    for line in status_stream:
                        if line.startswith("VmRSS:"):
                            total_kb += int(line.split()[1])
                            break
            except (OSError, ValueError, IndexError):
                continue
        return total_kb / 1024.0

    def sample_resources(self):
        elapsed = self.elapsed()
        if elapsed - self.last_resource_s < self.resource_period_s:
            return
        elapsed_sim = (
            None
            if self.latest_clock_s is None or self.first_clock_s is None
            else self.latest_clock_s - self.first_clock_s
        )
        realtime_factor = (
            None if elapsed_sim is None or elapsed <= 0.0 else elapsed_sim / elapsed
        )
        try:
            load_1m = os.getloadavg()[0]
        except (AttributeError, OSError):
            load_1m = None
        cpu_percent = self.system_cpu_percent()
        available = self.memory_available_mb()
        ros_rss = self.ros_process_rss_mb()
        rss = self.recorder_rss_mb()
        self.resources_writer.writerow(
            {
                "elapsed_wall_s": f"{elapsed:.6f}",
                "elapsed_sim_s": (
                    "" if elapsed_sim is None else f"{elapsed_sim:.6f}"
                ),
                "realtime_factor": (
                    "" if realtime_factor is None else f"{realtime_factor:.6f}"
                ),
                "load_1m": "" if load_1m is None else f"{load_1m:.6f}",
                "system_cpu_percent": (
                    "" if cpu_percent is None else f"{cpu_percent:.3f}"
                ),
                "memory_available_mb": (
                    "" if available is None else f"{available:.3f}"
                ),
                "ros_process_rss_mb": (
                    "" if ros_rss is None else f"{ros_rss:.3f}"
                ),
                "recorder_rss_mb": "" if rss is None else f"{rss:.3f}",
            }
        )
        self.resources_stream.flush()
        self.last_resource_s = elapsed

    def write_first_seen(self):
        path = os.path.join(self.evidence_dir, "occupancy_first_seen.csv")
        with open(path, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("voxel_x", "voxel_y", "voxel_z", "first_seen_s"))
            for voxel, first_seen in sorted(
                self.first_seen_voxels.items(),
                key=lambda item: (item[1], item[0]),
            ):
                writer.writerow((*voxel, f"{first_seen:.6f}"))

    def close(self):
        if self.closed:
            return
        self.sample_map()
        self.sample_resources()
        self.write_first_seen()
        for stream in (
            self.trajectory_stream,
            self.map_growth_stream,
            self.planning_stream,
            self.resources_stream,
            self.events_stream,
            self.planner_rosout_stream,
        ):
            stream.flush()
            stream.close()
        self.closed = True
        rospy.loginfo("Paper evidence saved to %s", self.evidence_dir)

    def run(self):
        deadline = time.monotonic() + self.duration_s
        rate = rospy.Rate(5.0)
        while not rospy.is_shutdown() and time.monotonic() < deadline:
            self.sample_map()
            self.sample_resources()
            if self.finished:
                rospy.sleep(2.0)
                break
            rate.sleep()
        self.close()


def main():
    rospy.init_node("fuel_paper_evidence_recorder")
    PaperEvidenceRecorder().run()


if __name__ == "__main__":
    main()
