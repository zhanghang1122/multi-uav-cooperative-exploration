#!/usr/bin/env python3
"""Publish presentation-only floor and obstacle views of FUEL occupancy.

FUEL can include a thin voxel layer at the configured upper map boundary in
``/sdf_map/occupancy_all``.  That layer is useful internally, but it obscures
an overhead view in RViz.  This node removes only points above a configured
visual ceiling, then separates the retained points into a floor slice and a
vertical-obstacle slice.  This makes the live map readable without altering
the map used by FUEL, the recorder, or offline evaluation.
"""

from __future__ import print_function

import argparse

import rospy
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2


class OnlineMapVisualizer(object):
    def __init__(self, args):
        self.args = args
        self.floor_publisher = rospy.Publisher(args.floor_output_topic, PointCloud2, queue_size=1)
        self.obstacle_publisher = rospy.Publisher(args.obstacle_output_topic, PointCloud2, queue_size=1)
        rospy.Subscriber(args.input_topic, PointCloud2, self.on_cloud, queue_size=1)
        rospy.loginfo(
            "RViz-only map split: %s -> (%s, %s); floor z <= %.2f m, suppressing z >= %.2f m",
            args.input_topic,
            args.floor_output_topic,
            args.obstacle_output_topic,
            args.floor_max_z_m,
            args.max_visible_z_m,
        )

    def on_cloud(self, message):
        # ROS Noetic's create_cloud_xyz32 calls len(points), so this must be a
        # concrete list rather than a generator expression.
        floor_points = []
        obstacle_points = []
        for x, y, z in point_cloud2.read_points(message, field_names=("x", "y", "z"), skip_nans=True):
            if z >= self.args.max_visible_z_m:
                continue
            if z <= self.args.floor_max_z_m:
                floor_points.append((x, y, z))
            else:
                obstacle_points.append((x, y, z))
        self.floor_publisher.publish(point_cloud2.create_cloud_xyz32(message.header, floor_points))
        self.obstacle_publisher.publish(point_cloud2.create_cloud_xyz32(message.header, obstacle_points))


def parse_args():
    parser = argparse.ArgumentParser(description="Split FUEL occupancy into RViz-only floor and obstacle views.")
    parser.add_argument("--input-topic", default="/sdf_map/occupancy_all")
    parser.add_argument("--floor-output-topic", default="/ruins_urban_01/online_floor_visual")
    parser.add_argument("--obstacle-output-topic", default="/ruins_urban_01/online_obstacle_visual")
    parser.add_argument("--floor-max-z-m", type=float, default=0.25)
    parser.add_argument("--max-visible-z-m", type=float, default=2.85)
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("ruins_online_map_visual_filter")
    OnlineMapVisualizer(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
