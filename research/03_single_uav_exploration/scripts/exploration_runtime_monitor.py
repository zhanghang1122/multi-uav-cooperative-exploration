#!/usr/bin/env python3
"""Record objective evidence from one official FUEL exploration run."""

import hashlib
import json
import math
import os
import time

import rospy
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Log
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2


class MessageStats:
    def __init__(self):
        self.messages = 0
        self.first_time_s = None
        self.last_time_s = None
        self.first_points = None
        self.max_points = 0

    def update(self, start_time, points=None):
        elapsed = time.monotonic() - start_time
        self.messages += 1
        if self.first_time_s is None:
            self.first_time_s = elapsed
        self.last_time_s = elapsed
        if points is not None:
            if self.first_points is None:
                self.first_points = points
            self.max_points = max(self.max_points, points)

    def as_dict(self):
        return {
            "messages": self.messages,
            "first_time_s": rounded(self.first_time_s),
            "last_time_s": rounded(self.last_time_s),
            "first_points": self.first_points,
            "max_points": self.max_points,
        }


def rounded(value):
    return None if value is None else round(value, 3)


class ExplorationRuntimeMonitor:
    def __init__(self):
        self.start_time = time.monotonic()
        self.duration_s = float(rospy.get_param("~duration_s", 900.0))
        self.result_file = rospy.get_param(
            "~result_file", "/tmp/ruins_fuel_exploration_runtime.json"
        )
        self.map_file = rospy.get_param(
            "~map_file", "/tmp/ruins_fuel_final_occupancy.pcd"
        )
        self.finish_log_text = rospy.get_param(
            "~finish_log_text", "finish exploration."
        )
        self.topics = {
            "odometry": rospy.get_param("~odom_topic", "/state_ukf/odom"),
            "trigger": rospy.get_param(
                "~trigger_topic", "/waypoint_generator/waypoints"
            ),
            "bspline": rospy.get_param("~bspline_topic", "/planning/bspline"),
            "position_command": rospy.get_param(
                "~position_command_topic", "/planning/pos_cmd"
            ),
            "occupancy": rospy.get_param(
                "~occupancy_topic", "/sdf_map/occupancy_all"
            ),
            "rosout": "/rosout_agg",
        }
        self.stats = {
            key: MessageStats()
            for key in ("odometry", "trigger", "bspline", "position_command", "occupancy")
        }
        self.previous_position = None
        self.path_length_m = 0.0
        self.finish_detected = False
        self.finish_time_s = None
        self.plan_fail_logs = 0
        self.collision_replan_logs = 0
        self.latest_occupancy = None
        self.subscribers = [
            rospy.Subscriber(
                self.topics["odometry"],
                Odometry,
                self.odometry_callback,
                queue_size=20,
            ),
            rospy.Subscriber(
                self.topics["occupancy"],
                PointCloud2,
                self.occupancy_callback,
                queue_size=3,
            ),
            rospy.Subscriber(
                self.topics["trigger"],
                rospy.AnyMsg,
                lambda _: self.stats["trigger"].update(self.start_time),
                queue_size=3,
            ),
            rospy.Subscriber(
                self.topics["bspline"],
                rospy.AnyMsg,
                lambda _: self.stats["bspline"].update(self.start_time),
                queue_size=10,
            ),
            rospy.Subscriber(
                self.topics["position_command"],
                rospy.AnyMsg,
                lambda _: self.stats["position_command"].update(self.start_time),
                queue_size=20,
            ),
            rospy.Subscriber(
                self.topics["rosout"],
                Log,
                self.log_callback,
                queue_size=100,
            ),
        ]

    def odometry_callback(self, message):
        self.stats["odometry"].update(self.start_time)
        point = message.pose.pose.position
        current = (point.x, point.y, point.z)
        if self.previous_position is not None:
            delta = math.sqrt(
                sum(
                    (current[index] - self.previous_position[index]) ** 2
                    for index in range(3)
                )
            )
            if delta < 1.0:
                self.path_length_m += delta
        self.previous_position = current

    def occupancy_callback(self, message):
        self.latest_occupancy = message
        self.stats["occupancy"].update(
            self.start_time, points=message.width * message.height
        )

    def log_callback(self, message):
        if "exploration_node" not in message.name:
            return
        if self.finish_log_text in message.msg:
            self.finish_detected = True
            if self.finish_time_s is None:
                self.finish_time_s = time.monotonic() - self.start_time
        if "plan fail" in message.msg.lower():
            self.plan_fail_logs += 1
        if "collision detected" in message.msg.lower():
            self.collision_replan_logs += 1

    def result(self, map_summary):
        occupancy = self.stats["occupancy"]
        checks = {
            "odometry_received": self.stats["odometry"].messages > 0,
            "exploration_trigger_received": self.stats["trigger"].messages > 0,
            "frontier_planner_published_bspline": self.stats["bspline"].messages > 0,
            "trajectory_server_published_commands": (
                self.stats["position_command"].messages > 0
            ),
            "online_occupancy_received": occupancy.messages > 0,
            "online_occupancy_grew": (
                occupancy.first_points is not None
                and occupancy.max_points > occupancy.first_points
            ),
            "fuel_reported_finish": self.finish_detected,
        }
        return {
            "schema_version": 1,
            "duration_s": rounded(time.monotonic() - self.start_time),
            "finish_time_s": rounded(self.finish_time_s),
            "path_length_m": round(self.path_length_m, 3),
            "topics": self.topics,
            "statistics": {
                key: value.as_dict() for key, value in self.stats.items()
            },
            "diagnostics": {
                "plan_fail_logs": self.plan_fail_logs,
                "collision_replan_logs": self.collision_replan_logs,
            },
            "outputs": {
                "final_occupancy_map": map_summary,
            },
            "checks": checks,
            "passed": all(checks.values()),
        }

    def save_occupancy_map(self):
        message = self.latest_occupancy
        if message is None:
            return {
                "path": self.map_file,
                "saved": False,
                "points": 0,
                "sha256": None,
            }

        points = list(
            point_cloud2.read_points(
                message,
                field_names=("x", "y", "z"),
                skip_nans=True,
            )
        )
        directory = os.path.dirname(os.path.abspath(self.map_file))
        os.makedirs(directory, exist_ok=True)
        with open(self.map_file, "w", encoding="ascii", newline="\n") as stream:
            stream.write("# .PCD v0.7 - Point Cloud Data file format\n")
            stream.write("VERSION 0.7\n")
            stream.write("FIELDS x y z\n")
            stream.write("SIZE 4 4 4\n")
            stream.write("TYPE F F F\n")
            stream.write("COUNT 1 1 1\n")
            stream.write(f"WIDTH {len(points)}\n")
            stream.write("HEIGHT 1\n")
            stream.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            stream.write(f"POINTS {len(points)}\n")
            stream.write("DATA ascii\n")
            for x, y, z in points:
                stream.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

        digest = hashlib.sha256()
        with open(self.map_file, "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return {
            "path": self.map_file,
            "saved": True,
            "points": len(points),
            "sha256": digest.hexdigest(),
        }

    def write(self):
        map_summary = self.save_occupancy_map()
        payload = self.result(map_summary)
        directory = os.path.dirname(os.path.abspath(self.result_file))
        os.makedirs(directory, exist_ok=True)
        with open(self.result_file, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        if payload["passed"]:
            rospy.loginfo("FUEL ruins exploration runtime validation passed.")
        else:
            failed = [key for key, value in payload["checks"].items() if not value]
            rospy.logerr(
                "FUEL ruins exploration runtime validation failed: %s",
                ", ".join(failed),
            )
        rospy.loginfo("Runtime report: %s", self.result_file)
        if map_summary["saved"]:
            rospy.loginfo(
                "Final online occupancy map: %s (%d points)",
                self.map_file,
                map_summary["points"],
            )

    def run(self):
        deadline = time.monotonic() + self.duration_s
        rate = rospy.Rate(5.0)
        while not rospy.is_shutdown() and time.monotonic() < deadline:
            if self.finish_detected:
                rospy.sleep(2.0)
                break
            rate.sleep()
        self.write()


def main():
    rospy.init_node("fuel_exploration_runtime_monitor")
    monitor = ExplorationRuntimeMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
