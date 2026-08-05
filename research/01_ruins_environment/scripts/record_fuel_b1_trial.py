#!/usr/bin/env python3
"""Read-only recorder for one FUEL B1 Frontier exploration trial.

The recorder never publishes a route, exploration goal, map, frontier or
planner parameter.  It observes FUEL's online map and trajectory interfaces,
then writes data needed for paper evaluation after FUEL reports completion.
"""

from __future__ import print_function

import argparse
import csv
import json
import math
import os
import time

import rospy
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Log
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2
from visualization_msgs.msg import Marker


DIAGNOSTIC_TOKENS = (
    "[fsm]",
    "finish exploration",
    "no coverable frontier",
    "frontier",
    "replan",
    "search fail",
    "failed",
    "no path",
    "kinodynamic",
    "total time too long",
)


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def stamp_seconds(stamp):
    return stamp.secs + stamp.nsecs * 1e-9


class TrialRecorder(object):
    def __init__(self, args):
        self.args = args
        os.makedirs(self.args.output_dir, exist_ok=True)
        self.started_monotonic = time.monotonic()
        write_json(os.path.join(self.args.output_dir, "recorder_startup.json"), {
            "schema_version": 1,
            "recorded_unix_s": time.time(),
            "node": "fuel_b1_trial_recorder",
            "arguments": vars(self.args),
            "interpretation": (
                "The read-only recorder reached initialization. This file does not prove "
                "that FUEL, map input, planning input, or completion detection succeeded."
            ),
        })
        self.last_position = None
        self.path_length_m = 0.0
        self.trajectory_rows = []
        self.map_growth_rows = []
        self.snapshot_rows = []
        self.last_trajectory_sample_s = -float("inf")
        self.last_map_sample_s = -float("inf")
        self.last_snapshot_s = -float("inf")
        self.snapshot_index = 0
        self.latest_cloud = None
        self.final_finish_time_s = None
        self.first_planner_message_s = None
        self.last_planner_message_s = None
        self.last_motion_s = None
        self.motion_reference_position = None
        self.planner_messages = 0
        self.frontier_messages = 0
        self.frontier_add_messages = 0
        self.frontier_delete_messages = 0
        self.recovery_events = 0
        self.received_odometry = False
        self.received_occupancy = False
        self.diagnostic_events = []

        rospy.Subscriber(args.odom_topic, Odometry, self.on_odometry, queue_size=100)
        rospy.Subscriber(args.occupancy_topic, PointCloud2, self.on_occupancy, queue_size=1)
        rospy.Subscriber(args.frontier_topic, Marker, self.on_frontier, queue_size=100)
        rospy.Subscriber(args.planner_topic, rospy.AnyMsg, self.on_planner, queue_size=100)
        rospy.Subscriber(args.rosout_topic, Log, self.on_rosout, queue_size=1000)
        rospy.loginfo(
            "B1 recorder is active. Waiting for FUEL map and completion; output directory: %s",
            self.args.output_dir,
        )

    def elapsed_s(self):
        return time.monotonic() - self.started_monotonic

    def on_odometry(self, message):
        if not self.received_odometry:
            self.received_odometry = True
            rospy.loginfo("B1 recorder received odometry on %s", self.args.odom_topic)
        position = message.pose.pose.position
        current = (position.x, position.y, position.z)
        elapsed = self.elapsed_s()
        if self.motion_reference_position is None:
            self.motion_reference_position = current
            self.last_motion_s = elapsed
        else:
            dx_ref = current[0] - self.motion_reference_position[0]
            dy_ref = current[1] - self.motion_reference_position[1]
            dz_ref = current[2] - self.motion_reference_position[2]
            displacement = math.sqrt(dx_ref * dx_ref + dy_ref * dy_ref + dz_ref * dz_ref)
            if displacement >= self.args.stall_motion_threshold_m:
                self.motion_reference_position = current
                self.last_motion_s = elapsed
        if self.last_position is not None:
            dx = current[0] - self.last_position[0]
            dy = current[1] - self.last_position[1]
            dz = current[2] - self.last_position[2]
            increment = math.sqrt(dx * dx + dy * dy + dz * dz)
            # Ignore a simulator reset or a corrupt odometry jump.
            if increment <= self.args.max_odom_increment_m:
                self.path_length_m += increment
        self.last_position = current

        if elapsed - self.last_trajectory_sample_s >= self.args.trajectory_sample_period_s:
            self.last_trajectory_sample_s = elapsed
            self.trajectory_rows.append((elapsed, stamp_seconds(message.header.stamp), current[0], current[1], current[2]))

    def on_occupancy(self, message):
        if not self.received_occupancy:
            self.received_occupancy = True
            rospy.loginfo("B1 recorder received online occupancy on %s", self.args.occupancy_topic)
        self.latest_cloud = message
        elapsed = self.elapsed_s()
        if elapsed - self.last_map_sample_s >= self.args.map_sample_period_s:
            self.last_map_sample_s = elapsed
            self.map_growth_rows.append((elapsed, int(message.width) * int(message.height)))
        if elapsed - self.last_snapshot_s >= self.args.snapshot_period_s:
            self.last_snapshot_s = elapsed
            self.save_snapshot(message, elapsed)

    def on_frontier(self, message):
        self.frontier_messages += 1
        if message.action == Marker.DELETE or message.action == Marker.DELETEALL:
            self.frontier_delete_messages += 1
        else:
            self.frontier_add_messages += 1

    def on_planner(self, _message):
        self.planner_messages += 1
        elapsed = self.elapsed_s()
        if self.first_planner_message_s is None:
            self.first_planner_message_s = elapsed
        self.last_planner_message_s = elapsed

    def on_rosout(self, message):
        text = message.msg.lower()
        if any(token in text for token in DIAGNOSTIC_TOKENS):
            self.diagnostic_events.append({
                "elapsed_s": round(self.elapsed_s(), 3),
                "level": int(message.level),
                "source": message.name,
                "message": message.msg,
            })
            if len(self.diagnostic_events) > self.args.rosout_history_size:
                self.diagnostic_events.pop(0)
        if self.args.recovery_log_token and self.args.recovery_log_token in message.msg:
            self.recovery_events += 1
        if "finish exploration." in text and self.final_finish_time_s is None:
            self.final_finish_time_s = self.elapsed_s()
            rospy.loginfo("FUEL completion detected; collecting final map for %.1f s.", self.args.settle_s)

    def classify_stall(self):
        """Provide evidence labels only; this function never controls FUEL."""
        messages = "\n".join(event["message"].lower() for event in self.diagnostic_events)
        if "finish exploration." in messages:
            return "fuel_reported_finish"
        if "no coverable frontier" in messages:
            return "no_coverable_frontier_reported"
        if "search fail" in messages or "kinodynamic" in messages or "no path" in messages:
            return "local_path_search_failure_reported"
        if self.first_planner_message_s is None:
            return "no_planner_message_after_recorder_start"
        if self.last_planner_message_s is not None and self.last_motion_s is not None:
            return "no_new_trajectory_and_no_motion"
        return "insufficient_runtime_evidence"

    def diagnostics(self, stop_reason):
        return {
            "schema_version": 1,
            "stop_reason": stop_reason,
            "observational_classification": self.classify_stall(),
            "last_planner_message_elapsed_s": (
                round(self.last_planner_message_s, 3) if self.last_planner_message_s is not None else None
            ),
            "last_motion_elapsed_s": round(self.last_motion_s, 3) if self.last_motion_s is not None else None,
            "first_planner_timeout_s": self.args.first_planner_timeout_s,
            "last_odometry_position_m": (
                [round(value, 4) for value in self.last_position] if self.last_position is not None else None
            ),
            "planner_messages": self.planner_messages,
            "frontier_messages": self.frontier_messages,
            "recent_relevant_rosout": self.diagnostic_events[-50:],
            "interpretation": (
                "Read-only diagnostic evidence. It does not infer ground truth, alter FUEL, "
                "supply a route, or prove that a reported planning failure is caused by geometry."
            ),
        }

    def write_csv(self, path, header, rows):
        with open(path, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def write_pcd(self, path, cloud=None):
        cloud = cloud or self.latest_cloud
        if cloud is None:
            raise RuntimeError("no online occupancy PointCloud2 was received")
        field_names = set(field.name for field in cloud.fields)
        required = set(("x", "y", "z"))
        if not required.issubset(field_names):
            raise RuntimeError("online occupancy cloud has no x/y/z fields")

        points = []
        for point in point_cloud2.read_points(cloud, field_names=("x", "y", "z"), skip_nans=True):
            points.append((float(point[0]), float(point[1]), float(point[2])))
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("# .PCD v0.7 - Point Cloud Data file format\n")
            stream.write("VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n")
            stream.write("WIDTH {}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {}\nDATA ascii\n".format(len(points), len(points)))
            for x, y, z in points:
                stream.write("{:.6f} {:.6f} {:.6f}\n".format(x, y, z))
        return len(points)

    def save_snapshot(self, cloud, elapsed):
        """Persist a read-only map snapshot for offline coverage-time evaluation."""
        snapshot_dir = os.path.join(self.args.output_dir, "snapshots")
        if not os.path.isdir(snapshot_dir):
            os.makedirs(snapshot_dir)
        filename = "occupancy_{:04d}.pcd".format(self.snapshot_index)
        path = os.path.join(snapshot_dir, filename)
        point_count = self.write_pcd(path, cloud)
        self.snapshot_rows.append((round(elapsed, 6), point_count, os.path.join("snapshots", filename)))
        self.snapshot_index += 1

    def run(self):
        rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            elapsed = self.elapsed_s()
            if self.final_finish_time_s is not None and elapsed >= self.final_finish_time_s + self.args.settle_s:
                stop_reason = "fuel_reported_finish"
                break
            if self.planner_stalled(elapsed):
                stop_reason = "planner_stall"
                rospy.logwarn(
                    "B1 recorder detected planner stall: no new B-spline and no %.3f m motion for %.1f s.",
                    self.args.stall_motion_threshold_m,
                    self.args.planner_stall_timeout_s,
                )
                break
            if self.first_planner_timed_out(elapsed):
                stop_reason = "planner_topic_timeout"
                rospy.logwarn(
                    "B1 recorder received no B-spline within %.1f s after startup.",
                    self.args.first_planner_timeout_s,
                )
                break
            if elapsed >= self.args.timeout_s:
                stop_reason = "timeout"
                break
            rate.sleep()
        else:
            stop_reason = "ros_shutdown"

        trajectory_path = os.path.join(self.args.output_dir, "trajectory.csv")
        growth_path = os.path.join(self.args.output_dir, "map_growth.csv")
        snapshots_path = os.path.join(self.args.output_dir, "snapshots.csv")
        map_path = os.path.join(self.args.output_dir, "final_online_occupancy.pcd")
        self.write_csv(trajectory_path, ("elapsed_s", "stamp_s", "x_m", "y_m", "z_m"), self.trajectory_rows)
        self.write_csv(growth_path, ("elapsed_s", "occupied_points"), self.map_growth_rows)
        self.write_csv(snapshots_path, ("elapsed_s", "occupied_points", "pcd_relative_path"), self.snapshot_rows)
        final_points = self.write_pcd(map_path)
        diagnostics_path = os.path.join(self.args.output_dir, "runtime_diagnostics.json")
        write_json(diagnostics_path, self.diagnostics(stop_reason))
        summary = {
            "schema_version": 3,
            "method_id": self.args.method_id,
            "scene": self.args.scene,
            "success": stop_reason == "fuel_reported_finish",
            "stop_reason": stop_reason,
            "duration_s": round(self.elapsed_s(), 3),
            "path_length_m": round(self.path_length_m, 3),
            "planner_messages": self.planner_messages,
            "frontier_messages": self.frontier_messages,
            "frontier_add_messages": self.frontier_add_messages,
            "frontier_delete_messages": self.frontier_delete_messages,
            "recovery_events": self.recovery_events,
            "final_occupied_points": final_points,
            "snapshot_count": len(self.snapshot_rows),
            "runtime_contract": {
                "read_only_recorder": True,
                "route_prior_used": False,
                "goal_prior_used": False,
                "truth_map_usage": "offline_evaluation_only",
                "planner_stall_rule": {
                    "definition": "After the first B-spline has been observed, terminate recording only when no new B-spline and no cumulative odometry displacement above the motion threshold are observed for the configured duration.",
                    "planner_stall_timeout_s": self.args.planner_stall_timeout_s,
                    "stall_motion_threshold_m": self.args.stall_motion_threshold_m,
                    "first_planner_timeout_s": self.args.first_planner_timeout_s,
                },
            },
            "recorded_topics": {
                "odometry": self.args.odom_topic,
                "online_occupancy": self.args.occupancy_topic,
                "frontier": self.args.frontier_topic,
                "planner": self.args.planner_topic,
            },
            "outputs": {
                "trajectory_csv": trajectory_path,
                "map_growth_csv": growth_path,
                "snapshots_csv": snapshots_path,
                "snapshots_directory": os.path.join(self.args.output_dir, "snapshots"),
                "final_online_occupancy_pcd": map_path,
                "runtime_diagnostics_json": diagnostics_path,
            },
        }
        write_json(os.path.join(self.args.output_dir, "trial_summary.json"), summary)
        print(json.dumps(summary, indent=2, sort_keys=True))

    def planner_stalled(self, elapsed):
        """Detect an observational failure condition without controlling FUEL."""
        if self.args.planner_stall_timeout_s <= 0.0:
            return False
        if self.first_planner_message_s is None or self.last_planner_message_s is None:
            return False
        if self.last_motion_s is None:
            return False
        no_trajectory_s = elapsed - self.last_planner_message_s
        no_motion_s = elapsed - self.last_motion_s
        return (
            no_trajectory_s >= self.args.planner_stall_timeout_s
            and no_motion_s >= self.args.planner_stall_timeout_s
        )

    def first_planner_timed_out(self, elapsed):
        """Fail closed when a recorder started with a running stack sees no planner."""
        return (
            self.args.first_planner_timeout_s > 0.0
            and self.first_planner_message_s is None
            and elapsed >= self.args.first_planner_timeout_s
        )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scene", default="e1_structured_interior")
    parser.add_argument(
        "--method-id",
        default="B1_fuel_frontier_single_uav",
        help="Identifier written to the trial summary; it never changes FUEL behavior.",
    )
    parser.add_argument(
        "--recovery-log-token",
        default="",
        help="Optional exact ROS log token used only to count recovery events.",
    )
    parser.add_argument("--timeout-s", type=float, default=1800.0)
    parser.add_argument("--settle-s", type=float, default=3.0)
    parser.add_argument("--map-sample-period-s", type=float, default=5.0)
    parser.add_argument(
        "--snapshot-period-s",
        type=float,
        default=20.0,
        help="Offline-map snapshot interval for T80/T90/T95 evaluation; never used by the planner.",
    )
    parser.add_argument("--trajectory-sample-period-s", type=float, default=0.2)
    parser.add_argument("--max-odom-increment-m", type=float, default=1.0)
    parser.add_argument(
        "--planner-stall-timeout-s",
        type=float,
        default=45.0,
        help="After FUEL has published at least one B-spline, record planner_stall when no new B-spline and no motion persist for this duration. Set to 0 to disable.",
    )
    parser.add_argument(
        "--first-planner-timeout-s",
        type=float,
        default=120.0,
        help="Record planner_topic_timeout when no B-spline is observed after recorder startup. Set to 0 to disable.",
    )
    parser.add_argument(
        "--stall-motion-threshold-m",
        type=float,
        default=0.05,
        help="Cumulative odometry displacement required to reset the planner-stall motion timer.",
    )
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--occupancy-topic", default="/sdf_map/occupancy_all")
    parser.add_argument("--frontier-topic", default="/planning_vis/frontier")
    parser.add_argument("--planner-topic", default="/planning/bspline")
    parser.add_argument("--rosout-topic", default="/rosout_agg")
    parser.add_argument(
        "--rosout-history-size",
        type=int,
        default=300,
        help="Number of relevant FUEL ROS log events retained for post-run diagnosis only.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.map_sample_period_s <= 0.0 or args.snapshot_period_s <= 0.0:
        raise SystemExit("map and snapshot sample periods must be positive")
    if (
        args.planner_stall_timeout_s < 0.0
        or args.first_planner_timeout_s < 0.0
        or args.stall_motion_threshold_m <= 0.0
        or args.rosout_history_size <= 0
    ):
        raise SystemExit("planner-stall timeout must be non-negative and its motion threshold must be positive")
    rospy.init_node("fuel_b1_trial_recorder", anonymous=False)
    TrialRecorder(args).run()


if __name__ == "__main__":
    main()
