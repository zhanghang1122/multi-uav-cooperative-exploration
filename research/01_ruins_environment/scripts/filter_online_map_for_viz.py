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
import math

import rospy
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Header


class OnlineMapVisualizer(object):
    def __init__(self, args):
        self.args = args
        self.floor_publisher = rospy.Publisher(args.floor_output_topic, PointCloud2, queue_size=1)
        self.obstacle_publisher = rospy.Publisher(args.obstacle_output_topic, PointCloud2, queue_size=1)
        self.last_publish_s = None
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
        now = rospy.get_time()
        if self.last_publish_s is not None and now - self.last_publish_s < self.args.min_publish_period_s:
            return

        # ROS Noetic's create_cloud_xyz32 calls len(points), so this must be a
        # concrete list rather than a generator expression.
        floor_points = []
        obstacle_points = []
        floor_voxels = set()
        obstacle_voxels = set()
        for x, y, z in point_cloud2.read_points(message, field_names=("x", "y", "z"), skip_nans=True):
            if z >= self.args.max_visible_z_m:
                continue
            voxel = (
                int(math.floor(x / self.args.visual_voxel_size_m)),
                int(math.floor(y / self.args.visual_voxel_size_m)),
                int(math.floor(z / self.args.visual_voxel_size_m)),
            )
            if z <= self.args.floor_max_z_m:
                if voxel not in floor_voxels:
                    floor_voxels.add(voxel)
                    floor_points.append((x, y, z))
            else:
                if voxel not in obstacle_voxels:
                    obstacle_voxels.add(voxel)
                    obstacle_points.append((x, y, z))
        # FUEL's simulator can label world-coordinate occupancy with its
        # simulator frame.  This is a visualization-only relabel so RViz does
        # not require an unavailable simulator-to-world TF transform.
        header = Header(seq=message.header.seq, stamp=message.header.stamp, frame_id=self.args.display_frame)
        self.floor_publisher.publish(point_cloud2.create_cloud_xyz32(header, floor_points))
        self.obstacle_publisher.publish(point_cloud2.create_cloud_xyz32(header, obstacle_points))
        self.last_publish_s = now


def parse_args():
    parser = argparse.ArgumentParser(description="Split FUEL occupancy into RViz-only floor and obstacle views.")
    parser.add_argument("--input-topic", default="/sdf_map/occupancy_all")
    parser.add_argument("--floor-output-topic", default="/ruins_urban_01/online_floor_visual")
    parser.add_argument("--obstacle-output-topic", default="/ruins_urban_01/online_obstacle_visual")
    parser.add_argument("--floor-max-z-m", type=float, default=0.25)
    parser.add_argument("--max-visible-z-m", type=float, default=2.85)
    parser.add_argument("--display-frame", default="world")
    parser.add_argument("--visual-voxel-size-m", type=float, default=0.15)
    parser.add_argument("--min-publish-period-s", type=float, default=0.8)
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("ruins_online_map_visual_filter")
    OnlineMapVisualizer(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
