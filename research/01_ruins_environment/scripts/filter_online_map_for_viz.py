#!/usr/bin/env python3
"""Publish a presentation-only view of FUEL's online occupancy map.

FUEL can include a thin voxel layer at the configured upper map boundary in
``/sdf_map/occupancy_all``.  That layer is useful internally, but it obscures
an overhead view in RViz.  This node removes only points above a configured
visual ceiling.  It never feeds FUEL, the trial recorder, or map evaluation.
"""

from __future__ import print_function

import argparse

import rospy
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2


class OnlineMapVisualizer(object):
    def __init__(self, args):
        self.args = args
        self.publisher = rospy.Publisher(args.output_topic, PointCloud2, queue_size=1)
        rospy.Subscriber(args.input_topic, PointCloud2, self.on_cloud, queue_size=1)
        rospy.loginfo(
            "RViz-only map filter: %s -> %s; suppressing z >= %.2f m",
            args.input_topic,
            args.output_topic,
            args.max_visible_z_m,
        )

    def on_cloud(self, message):
        points = (
            (x, y, z)
            for x, y, z in point_cloud2.read_points(message, field_names=("x", "y", "z"), skip_nans=True)
            if z < self.args.max_visible_z_m
        )
        self.publisher.publish(point_cloud2.create_cloud_xyz32(message.header, points))


def parse_args():
    parser = argparse.ArgumentParser(description="Filter upper map-boundary voxels for RViz only.")
    parser.add_argument("--input-topic", default="/sdf_map/occupancy_all")
    parser.add_argument("--output-topic", default="/ruins_urban_01/online_occupancy_visual")
    parser.add_argument("--max-visible-z-m", type=float, default=4.0)
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("ruins_online_map_visual_filter")
    OnlineMapVisualizer(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
