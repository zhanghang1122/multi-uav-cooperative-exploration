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
from sensor_msgs.msg import Image


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
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--depth-topic", default="/pcl_render_node/depth")
    parser.add_argument("--sensor-pose-topic", default="/pcl_render_node/sensor_pose")
    parser.add_argument(
        "--collision-diameter-m",
        type=positive_float,
        required=True,
        help="Measured maximum collision diameter of the simulated UAV body, excluding clearance.",
    )
    parser.add_argument(
        "--safety-margin-m",
        type=positive_float,
        required=True,
        help="Per-side planning margin. It is added on both sides of the collision diameter.",
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


def main():
    args = parse_args()
    rospy.init_node("ruins_platform_profile_collector", anonymous=True)

    odom = TopicSample(args.odom_topic, "nav_msgs/Odometry")
    depth = TopicSample(args.depth_topic, "sensor_msgs/Image")
    sensor_pose = TopicSample(args.sensor_pose_topic, "geometry_msgs/PoseStamped")

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

    rospy.Subscriber(args.odom_topic, Odometry, on_odom, queue_size=20)
    rospy.Subscriber(args.depth_topic, Image, on_depth, queue_size=5)
    rospy.Subscriber(args.sensor_pose_topic, PoseStamped, on_sensor_pose, queue_size=20)

    deadline = time.time() + args.duration_s
    rate = rospy.Rate(20)
    rospy.loginfo("Sampling platform interfaces for %.1f seconds.", args.duration_s)
    while not rospy.is_shutdown() and time.time() < deadline:
        rate.sleep()

    effective_diameter = args.collision_diameter_m + 2.0 * args.safety_margin_m
    topics = {
        "odometry": odom.as_dict(),
        "depth": depth.as_dict(),
        "sensor_pose": sensor_pose.as_dict(),
    }
    failures = []
    for key, sample in topics.items():
        if sample["received_messages"] == 0:
            failures.append("missing_%s" % key)
        if not sample["frame_id"]:
            failures.append("missing_%s_frame" % key)
    if odom.frame_id and sensor_pose.frame_id and odom.frame_id != sensor_pose.frame_id:
        failures.append("odom_sensor_pose_frame_mismatch")
    if depth.frame_id and sensor_pose.frame_id and depth.frame_id == sensor_pose.frame_id:
        # The depth image normally belongs to the sensor frame; a pose normally
        # belongs to a world/map frame. Equality deserves explicit review.
        failures.append("depth_and_sensor_pose_share_frame_review_required")

    profile = {
        "schema_version": 1,
        "profile_kind": "measured_ros_platform_interface",
        "captured_at_unix_s": round(time.time(), 3),
        "sampling_duration_s": args.duration_s,
        "map_resolution_m": args.map_resolution_m,
        "vehicle": {
            "collision_diameter_m": args.collision_diameter_m,
            "safety_margin_per_side_m": args.safety_margin_m,
            "effective_planning_diameter_m": round(effective_diameter, 6),
            "dimension_source": "experimenter-measured collision geometry",
        },
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
        rospy.logerr("Platform profile is incomplete: %s", ", ".join(failures))
        return 1
    rospy.loginfo("Platform profile passed: %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
