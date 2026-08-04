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
import math

import rospy
from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
from visualization_msgs.msg import Marker


class UavPoseMarker(object):
    def __init__(self, args):
        self.args = args
        self.publisher = rospy.Publisher(args.output_topic, Marker, queue_size=1)
        rospy.Subscriber(args.odom_topic, Odometry, self.on_odometry, queue_size=10)
        self.executed_path = []
        self.last_path_point = None
        rospy.loginfo("RViz-only UAV marker: %s -> %s", args.odom_topic, args.output_topic)

    def on_odometry(self, message):
        pose = message.pose.pose
        point = pose.position
        if self._should_append(point):
            self.executed_path.append(Point(point.x, point.y, point.z))
            if len(self.executed_path) > self.args.max_path_points:
                self.executed_path.pop(0)
            self.last_path_point = Point(point.x, point.y, point.z)

        self.publisher.publish(self._arrow_marker(message.header, pose))
        self.publisher.publish(self._position_marker(message.header, point))
        self.publisher.publish(self._path_marker(message.header))

    def _should_append(self, point):
        if self.last_path_point is None:
            return True
        return math.sqrt(
            (point.x - self.last_path_point.x) ** 2
            + (point.y - self.last_path_point.y) ** 2
            + (point.z - self.last_path_point.z) ** 2
        ) >= self.args.path_spacing_m

    def _base_marker(self, header, namespace, marker_id):
        marker = Marker()
        marker.header.stamp = header.stamp
        # The simulator's odometry frame has no TF link for RViz.  E2 uses
        # world coordinates numerically, so this is an RViz-only display frame.
        marker.header.frame_id = self.args.display_frame
        marker.ns = namespace
        marker.id = marker_id
        marker.action = Marker.ADD
        return marker

    def _arrow_marker(self, header, pose):
        marker = self._base_marker(header, "uav_heading", 0)
        marker.type = Marker.ARROW
        marker.pose = pose
        marker.scale.x = 0.95
        marker.scale.y = 0.26
        marker.scale.z = 0.26
        marker.color.r = 0.85
        marker.color.g = 0.12
        marker.color.b = 0.10
        marker.color.a = 1.0
        return marker

    def _position_marker(self, header, point):
        marker = self._base_marker(header, "uav_position", 1)
        marker.type = Marker.SPHERE
        marker.pose.position = point
        marker.pose.orientation.w = 1.0
        marker.scale.x = 0.32
        marker.scale.y = 0.32
        marker.scale.z = 0.32
        marker.color.r = 0.85
        marker.color.g = 0.12
        marker.color.b = 0.10
        marker.color.a = 1.0
        return marker

    def _path_marker(self, header):
        marker = self._base_marker(header, "executed_path", 2)
        marker.type = Marker.LINE_STRIP
        marker.scale.x = 0.055
        marker.color.r = 0.03
        marker.color.g = 0.10
        marker.color.b = 0.28
        marker.color.a = 1.0
        marker.points = self.executed_path
        return marker


def parse_args():
    parser = argparse.ArgumentParser(description="Publish a visible UAV marker for FUEL RViz runs.")
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--output-topic", default="/ruins_urban_01/uav_pose_marker")
    parser.add_argument("--display-frame", default="world")
    parser.add_argument("--path-spacing-m", type=float, default=0.08)
    parser.add_argument("--max-path-points", type=int, default=6000)
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("ruins_uav_pose_marker")
    UavPoseMarker(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
