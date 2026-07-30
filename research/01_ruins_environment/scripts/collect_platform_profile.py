#!/usr/bin/env python3
"""Capture measured ROS interfaces for a reproducible exploration platform.

This node is deliberately passive: it never publishes a goal, a trajectory,
map data, TF, or simulator control command.  Its output is a platform profile
that separates measured runtime interfaces from vehicle dimensions supplied by
the experimenter.  Scene generators may consume a profile only after it passes.
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import time

import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, PointCloud2


SENSOR_STACK_DEFAULTS = {
    "marsim-os128": {
        "odom_topic": "/quad_0/lidar_slam/odom",
        "cloud_topic": "/quad0_pcl_render_node/sensor_cloud",
    },
    "fuel-depth": {
        "odom_topic": "/state_ukf/odom",
        "depth_topic": "/pcl_render_node/depth",
        "sensor_pose_topic": "/pcl_render_node/sensor_pose",
    },
}


class TopicSample(object):
    def __init__(self, topic, message_kind):
        self.topic = topic
        self.message_kind = message_kind
        self.count = 0
        self.first_receipt_s = None
        self.last_receipt_s = None
        self.frame_id = None
        self.details = {}

    def record(self, message):
        now_s = time.time()
        if self.first_receipt_s is None:
            self.first_receipt_s = now_s
        self.last_receipt_s = now_s
        self.count += 1
        if hasattr(message, "header"):
            self.frame_id = message.header.frame_id.lstrip("/")

    def as_dict(self):
        rate_hz = 0.0
        if self.count > 1 and self.last_receipt_s > self.first_receipt_s:
            rate_hz = (self.count - 1) / (self.last_receipt_s - self.first_receipt_s)
        return {
            "topic": self.topic,
            "message_kind": self.message_kind,
            "received_messages": self.count,
            "observed_rate_hz": round(rate_hz, 3),
            "frame_id": self.frame_id,
            "details": self.details,
        }


def positive_float(value):
    parsed = float(value)
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Passively measure the ROS interfaces used by the exploration platform."
    )
    parser.add_argument("--output", required=True, help="Profile JSON written after sampling.")
    parser.add_argument("--duration-s", type=positive_float, default=12.0)
    parser.add_argument(
        "--sensor-stack",
        choices=sorted(SENSOR_STACK_DEFAULTS),
        default="marsim-os128",
        help="Measured ROS interface family. The default matches MARSIM OS128.",
    )
    parser.add_argument("--odom-topic", help="Override the stack default odometry topic.")
    parser.add_argument("--cloud-topic", help="Override the MARSIM PointCloud2 topic.")
    parser.add_argument("--depth-topic", help="Override the FUEL depth-image topic.")
    parser.add_argument("--sensor-pose-topic", help="Override the FUEL sensor-pose topic.")
    parser.add_argument(
        "--collision-diameter-m",
        type=positive_float,
        help="Optional measured UAV collision diameter, excluding clearance.",
    )
    parser.add_argument(
        "--safety-margin-m",
        type=positive_float,
        help="Optional per-side planning margin. Supply this only with --collision-diameter-m.",
    )
    parser.add_argument(
        "--effective-planning-diameter-m",
        type=positive_float,
        help=(
            "Direct planner safety-envelope diameter. Use this instead of collision diameter "
            "+ margin when the active planner already inflates obstacles."
        ),
    )
    parser.add_argument(
        "--planning-envelope-source",
        help="Required provenance when --effective-planning-diameter-m is used.",
    )
    parser.add_argument("--map-resolution-m", type=positive_float, default=0.10)
    return parser.parse_args()


def write_json(path, value):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def resolved_topic(args, name):
    override = getattr(args, name)
    if override:
        return override
    return SENSOR_STACK_DEFAULTS[args.sensor_stack].get(name)


def main():
    args = parse_args()
    collision_model_supplied = args.collision_diameter_m is not None
    direct_envelope_supplied = args.effective_planning_diameter_m is not None
    if collision_model_supplied != (args.safety_margin_m is not None):
        raise SystemExit(
            "--collision-diameter-m and --safety-margin-m must be supplied together or both omitted"
        )
    if collision_model_supplied and direct_envelope_supplied:
        raise SystemExit(
            "use either collision diameter + safety margin or --effective-planning-diameter-m, not both"
        )
    if direct_envelope_supplied and not args.planning_envelope_source:
        raise SystemExit("--planning-envelope-source is required with --effective-planning-diameter-m")
    if args.planning_envelope_source and not direct_envelope_supplied:
        raise SystemExit("--planning-envelope-source requires --effective-planning-diameter-m")
    rospy.init_node("ruins_platform_profile_collector", anonymous=True)

    odom_topic = resolved_topic(args, "odom_topic")
    cloud_topic = resolved_topic(args, "cloud_topic")
    depth_topic = resolved_topic(args, "depth_topic")
    sensor_pose_topic = resolved_topic(args, "sensor_pose_topic")

    odom = TopicSample(odom_topic, "nav_msgs/Odometry")
    cloud = TopicSample(cloud_topic, "sensor_msgs/PointCloud2") if cloud_topic else None
    depth = TopicSample(depth_topic, "sensor_msgs/Image") if depth_topic else None
    sensor_pose = (
        TopicSample(sensor_pose_topic, "geometry_msgs/PoseStamped") if sensor_pose_topic else None
    )

    def on_odom(message):
        odom.record(message)

    def on_depth(message):
        depth.record(message)
        depth.details = {
            "width_px": message.width,
            "height_px": message.height,
            "encoding": message.encoding,
            "step_bytes": message.step,
        }

    def on_sensor_pose(message):
        sensor_pose.record(message)

    def on_cloud(message):
        cloud.record(message)
        cloud.details = {
            "width_points": message.width,
            "height_points": message.height,
            "point_step_bytes": message.point_step,
            "row_step_bytes": message.row_step,
            "is_dense": message.is_dense,
        }

    rospy.Subscriber(odom_topic, Odometry, on_odom, queue_size=20)
    if cloud is not None:
        rospy.Subscriber(cloud_topic, PointCloud2, on_cloud, queue_size=5)
    if depth is not None:
        rospy.Subscriber(depth_topic, Image, on_depth, queue_size=5)
    if sensor_pose is not None:
        rospy.Subscriber(sensor_pose_topic, PoseStamped, on_sensor_pose, queue_size=20)

    deadline = time.time() + args.duration_s
    rate = rospy.Rate(20)
    rospy.loginfo("Sampling platform interfaces for %.1f seconds.", args.duration_s)
    while not rospy.is_shutdown() and time.time() < deadline:
        rate.sleep()

    geometry_ready = collision_model_supplied or direct_envelope_supplied
    effective_diameter = None
    dimension_source = "not recorded; interface audit only"
    if collision_model_supplied:
        effective_diameter = args.collision_diameter_m + 2.0 * args.safety_margin_m
        dimension_source = "experimenter-measured collision geometry plus per-side margin"
    elif direct_envelope_supplied:
        effective_diameter = args.effective_planning_diameter_m
        dimension_source = args.planning_envelope_source
    topics = {"odometry": odom.as_dict()}
    if cloud is not None:
        topics["lidar_cloud"] = cloud.as_dict()
    if depth is not None:
        topics["depth"] = depth.as_dict()
    if sensor_pose is not None:
        topics["sensor_pose"] = sensor_pose.as_dict()
    failures = []
    for key, sample in topics.items():
        if sample["received_messages"] == 0:
            failures.append("missing_%s" % key)
        if not sample["frame_id"]:
            failures.append("missing_%s_frame" % key)
    if sensor_pose is not None and odom.frame_id and sensor_pose.frame_id and odom.frame_id != sensor_pose.frame_id:
        failures.append("odom_sensor_pose_frame_mismatch")
    if depth is not None and sensor_pose is not None and depth.frame_id and sensor_pose.frame_id and depth.frame_id == sensor_pose.frame_id:
        # The depth image normally belongs to the sensor frame; a pose normally
        # belongs to a world/map frame. Equality deserves explicit review.
        failures.append("depth_and_sensor_pose_share_frame_review_required")

    vehicle = {
        "collision_diameter_m": args.collision_diameter_m,
        "safety_margin_per_side_m": args.safety_margin_m,
        "effective_planning_diameter_m": (
            round(effective_diameter, 6) if effective_diameter is not None else None
        ),
        "dimension_source": dimension_source,
    }
    profile = {
        "schema_version": 1,
        "profile_kind": "measured_ros_platform_interface",
        "sensor_stack": args.sensor_stack,
        "captured_at_unix_s": round(time.time(), 3),
        "sampling_duration_s": args.duration_s,
        "map_resolution_m": args.map_resolution_m,
        "vehicle": vehicle,
        "geometry_ready": geometry_ready,
        "topics": topics,
        "passed": not failures,
        "failures": failures,
        "interpretation": (
            "Passive interface audit only. This file contains no route, goal, "
            "prior map, frontier, or scene topology."
        ),
    }
    write_json(args.output, profile)
    print(json.dumps(profile, indent=2, sort_keys=True))
    if failures:
        rospy.logerr("Platform interface audit is incomplete: %s", ", ".join(failures))
        return 1
    if geometry_ready:
        rospy.loginfo("Platform profile passed and is ready for geometry derivation: %s", args.output)
    else:
        rospy.loginfo("Platform interface audit passed; add measured geometry before scene derivation: %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
