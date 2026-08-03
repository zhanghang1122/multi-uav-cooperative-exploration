#!/usr/bin/env python3
"""Publish a robust RViz-only UAV pose marker from FUEL odometry.

The FUEL simulator may label its odometry with a frame that does not have a
published TF link to RViz's ``world`` frame.  The planning stack uses the
numeric state correctly, but RViz then hides an Odometry display.  The marker
below explicitly uses the common planning frame for the E2 benchmark.  It is
strictly visual and does not publish state back to the planner.
"""

from __future__ import print_function

import argparse

import rospy
from nav_msgs.msg import Odometry
from visualization_msgs.msg import Marker


class UavPoseMarker(object):
    def __init__(self, args):
        self.args = args
        self.publisher = rospy.Publisher(args.output_topic, Marker, queue_size=1)
        rospy.Subscriber(args.odom_topic, Odometry, self.on_odometry, queue_size=10)
        rospy.loginfo("RViz-only UAV marker: %s -> %s", args.odom_topic, args.output_topic)

    def on_odometry(self, message):
        marker = Marker()
        marker.header.stamp = message.header.stamp
        marker.header.frame_id = self.args.display_frame
        marker.ns = "uav_pose"
        marker.id = 0
        marker.type = Marker.ARROW
        marker.action = Marker.ADD
        marker.pose = message.pose.pose
        marker.scale.x = 0.90
        marker.scale.y = 0.22
        marker.scale.z = 0.22
        marker.color.r = 1.0
        marker.color.g = 0.30
        marker.color.b = 0.02
        marker.color.a = 1.0
        self.publisher.publish(marker)


def parse_args():
    parser = argparse.ArgumentParser(description="Publish a visible UAV marker for FUEL RViz runs.")
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--output-topic", default="/ruins_urban_01/uav_pose_marker")
    parser.add_argument("--display-frame", default="world")
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("ruins_uav_pose_marker")
    UavPoseMarker(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
