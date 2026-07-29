#!/usr/bin/env python3
"""Record reproducible evidence from one autonomous FUEL exploration run.

The recorder is observation-only.  It never loads a truth map, publishes a
navigation command, or changes FUEL parameters.  The final PCD comes solely
from the independent OctoMap topic used for reconstruction evaluation.
"""

import argparse
import csv
import json
import math
import os
import time


PCD_HEADER = """# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH {count}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {count}\nDATA ascii\n"""


def voxel_key(point, resolution):
    """Return a stable nearest-voxel key for an XYZ point."""
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    return tuple(int(math.floor(coordinate / resolution + 0.5)) for coordinate in point)


def voxelize_points(points, resolution):
    """Deduplicate points by voxel while retaining an observed XYZ center."""
    voxels = {}
    for point in points:
        if len(point) < 3 or not all(math.isfinite(value) for value in point[:3]):
            continue
        xyz = (float(point[0]), float(point[1]), float(point[2]))
        voxels[voxel_key(xyz, resolution)] = xyz
    return voxels


def write_ascii_pcd(path, points):
    """Write XYZ points in the portable PCD format used by offline evaluators."""
    ordered = sorted((float(x), float(y), float(z)) for x, y, z in points)
    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write(PCD_HEADER.format(count=len(ordered)))
        for x, y, z in ordered:
            handle.write("%.6f %.6f %.6f\n" % (x, y, z))


def distance_xyz(first, second):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class TrialRecorder:
    def __init__(self, rospy, point_cloud2, odometry_type, cloud_type, log_type, arguments):
        self.rospy = rospy
        self.point_cloud2 = point_cloud2
        self.arguments = arguments
        self.started_monotonic = None
        self.finished_monotonic = None
        self.finish_detected = False
        self.timed_out = False
        self.finalized = False
        self.planner_messages = 0
        self.latest_voxels = {}
        self.map_growth = []
        self.trajectory = []
        self.path_length_m = 0.0
        self.last_trajectory_point = None
        self.last_trajectory_sample = None
        self.last_map_sample = None
        self.last_snapshot = None
        self.snapshot_count = 0
        self.output_dir = os.path.abspath(arguments.output_dir)
        if os.path.exists(self.output_dir) and os.listdir(self.output_dir):
            raise ValueError("output directory is not empty: %s" % self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        rospy.Subscriber(arguments.odom_topic, odometry_type, self.odometry_callback, queue_size=50)
        rospy.Subscriber(arguments.occupancy_topic, cloud_type, self.occupancy_callback, queue_size=2)
        rospy.Subscriber(arguments.planner_topic, rospy.AnyMsg, self.planner_callback, queue_size=5)
        rospy.Subscriber(arguments.rosout_topic, log_type, self.rosout_callback, queue_size=100)
        rospy.Timer(rospy.Duration(0.5), self.timer_callback)
        rospy.on_shutdown(self.shutdown_callback)
        rospy.loginfo("Trial recorder is observation-only: %s, %s, %s", arguments.odom_topic,
                      arguments.occupancy_topic, arguments.planner_topic)

    def elapsed_s(self):
        if self.started_monotonic is None:
            return 0.0
        end = self.finished_monotonic if self.finished_monotonic is not None else time.monotonic()
        return max(0.0, end - self.started_monotonic)

    def odometry_callback(self, message):
        now = time.monotonic()
        if self.started_monotonic is None:
            self.started_monotonic = now
        point = (message.pose.pose.position.x, message.pose.pose.position.y, message.pose.pose.position.z)
        if self.last_trajectory_point is not None:
            self.path_length_m += distance_xyz(self.last_trajectory_point, point)
        self.last_trajectory_point = point
        if self.last_trajectory_sample is None or now - self.last_trajectory_sample >= self.arguments.trajectory_sample_period_s:
            self.trajectory.append((self.elapsed_s(), point[0], point[1], point[2]))
            self.last_trajectory_sample = now

    def occupancy_callback(self, message):
        if self.started_monotonic is None:
            self.started_monotonic = time.monotonic()
        points = self.point_cloud2.read_points(message, field_names=("x", "y", "z"), skip_nans=True)
        self.latest_voxels = voxelize_points(points, self.arguments.map_resolution_m)
        now = time.monotonic()
        if self.last_map_sample is None or now - self.last_map_sample >= self.arguments.map_sample_period_s:
            snapshot_path = ""
            if self.last_snapshot is None or now - self.last_snapshot >= self.arguments.snapshot_period_s:
                self.snapshot_count += 1
                snapshots_dir = os.path.join(self.output_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                snapshot_name = "map_%03d_%06ds.pcd" % (self.snapshot_count, int(self.elapsed_s()))
                snapshot_path = os.path.join(snapshots_dir, snapshot_name)
                write_ascii_pcd(snapshot_path, self.latest_voxels.values())
                self.last_snapshot = now
            self.map_growth.append((self.elapsed_s(), len(self.latest_voxels), snapshot_path))
            self.last_map_sample = now

    def planner_callback(self, _message):
        self.planner_messages += 1

    def rosout_callback(self, message):
        if self.finish_detected:
            return
        if self.arguments.finish_log_text in message.msg:
            self.finish_detected = True
            self.finished_monotonic = time.monotonic()
            self.rospy.loginfo("FUEL completion log observed; finalizing independent trial evidence.")
            self.finalize("fuel_reported_finish")
            self.rospy.signal_shutdown("FUEL reported exploration completion")

    def timer_callback(self, _event):
        if self.started_monotonic is None or self.finalized:
            return
        if self.elapsed_s() >= self.arguments.max_duration_s:
            self.timed_out = True
            self.finished_monotonic = time.monotonic()
            self.rospy.logwarn("Trial time limit reached; saving incomplete-run evidence.")
            self.finalize("time_limit")
            self.rospy.signal_shutdown("trial time limit reached")

    def write_csv(self, path, columns, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)

    def finalize(self, stop_reason):
        if self.finalized:
            return
        self.finalized = True
        if self.finished_monotonic is None:
            self.finished_monotonic = time.monotonic()
        final_pcd = os.path.join(self.output_dir, "final_independent_octomap.pcd")
        trajectory_csv = os.path.join(self.output_dir, "trajectory.csv")
        growth_csv = os.path.join(self.output_dir, "map_growth.csv")
        write_ascii_pcd(final_pcd, self.latest_voxels.values())
        self.write_csv(trajectory_csv, ("elapsed_s", "x_m", "y_m", "z_m"), self.trajectory)
        self.write_csv(growth_csv, ("elapsed_s", "occupied_voxels", "snapshot_pcd"), self.map_growth)
        summary = {
            "schema_version": 1,
            "method_id": self.arguments.method_id,
            "scene_variant": self.arguments.scene_variant,
            "stop_reason": stop_reason,
            "success": bool(self.finish_detected and self.latest_voxels and self.planner_messages),
            "duration_s": round(self.elapsed_s(), 3),
            "path_length_m": round(self.path_length_m, 3),
            "planner_messages": self.planner_messages,
            "final_occupied_voxels": len(self.latest_voxels),
            "snapshot_count": self.snapshot_count,
            "truth_map_usage": "offline_evaluation_only",
            "route_prior_used": False,
            "waypoint_prior_used": False,
            "recorded_topics": {
                "odometry": self.arguments.odom_topic,
                "independent_occupancy": self.arguments.occupancy_topic,
                "planner": self.arguments.planner_topic,
                "rosout": self.arguments.rosout_topic,
            },
            "outputs": {
                "final_independent_octomap_pcd": final_pcd,
                "trajectory_csv": trajectory_csv,
                "map_growth_csv": growth_csv,
            },
        }
        with open(os.path.join(self.output_dir, "trial_summary.json"), "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        self.rospy.loginfo("Trial evidence saved to %s", self.output_dir)

    def shutdown_callback(self):
        self.finalize("ros_shutdown")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scene-variant", default="base")
    parser.add_argument("--method-id", default="B1_fuel_frontier_single_uav")
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--occupancy-topic", default="/octomap_point_cloud_centers")
    parser.add_argument("--planner-topic", default="/planning/bspline")
    parser.add_argument("--rosout-topic", default="/rosout_agg")
    parser.add_argument("--finish-log-text", default="finish exploration.")
    parser.add_argument("--map-resolution-m", type=float, default=0.1)
    parser.add_argument("--trajectory-sample-period-s", type=float, default=0.1)
    parser.add_argument("--map-sample-period-s", type=float, default=2.0)
    parser.add_argument("--snapshot-period-s", type=float, default=60.0)
    parser.add_argument("--max-duration-s", type=float, default=1800.0)
    arguments = parser.parse_args(argv)
    if min(arguments.map_resolution_m, arguments.trajectory_sample_period_s,
           arguments.map_sample_period_s, arguments.snapshot_period_s, arguments.max_duration_s) <= 0:
        parser.error("sampling intervals, resolution, and maximum duration must be positive")
    return arguments


def main():
    import rospy
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Log
    from sensor_msgs import point_cloud2
    from sensor_msgs.msg import PointCloud2

    rospy.init_node("ruins_single_uav_trial_recorder")
    arguments = parse_arguments(rospy.myargv()[1:])
    TrialRecorder(rospy, point_cloud2, Odometry, PointCloud2, Log, arguments)
    rospy.spin()


if __name__ == "__main__":
    main()
