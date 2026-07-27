#!/usr/bin/env python3
"""Publish a lightweight UAV marker and its measured odometry path."""

import copy
import math

import rospy
from geometry_msgs.msg import Point, PoseStamped
from nav_msgs.msg import Odometry, Path
from visualization_msgs.msg import Marker, MarkerArray


class UavVisualizer:
    def __init__(self):
        self.odom_topic = rospy.get_param(
            "~odom_topic", "/quad_0/lidar_slam/odom"
        )
        self.marker_topic = rospy.get_param(
            "~marker_topic", "/ruins/uav0_markers"
        )
        self.path_topic = rospy.get_param("~path_topic", "/ruins/uav0_path")
        self.world_frame = rospy.get_param("~world_frame", "world")
        self.sensor_frame = rospy.get_param("~sensor_frame", "sensor")
        self.max_path_points = int(rospy.get_param("~max_path_points", 5000))
        self.path_min_step = float(rospy.get_param("~path_min_step_m", 0.08))

        self.path = Path()
        self.path.header.frame_id = self.world_frame
        self.last_path_point = None

        self.marker_publisher = rospy.Publisher(
            self.marker_topic, MarkerArray, queue_size=1, latch=True
        )
        self.path_publisher = rospy.Publisher(
            self.path_topic, Path, queue_size=1, latch=True
        )
        self.subscriber = rospy.Subscriber(
            self.odom_topic, Odometry, self.odom_callback, queue_size=20
        )
        self.timer = rospy.Timer(rospy.Duration(0.2), self.publish_markers)

    @staticmethod
    def color(marker, red, green, blue, alpha=1.0):
        marker.color.r = red
        marker.color.g = green
        marker.color.b = blue
        marker.color.a = alpha

    def base_marker(self, marker_id, marker_type):
        marker = Marker()
        marker.header.frame_id = self.sensor_frame
        marker.header.stamp = rospy.Time(0)
        marker.ns = "ruins_uav0"
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.frame_locked = True
        return marker

    def build_markers(self):
        markers = []

        body = self.base_marker(0, Marker.CUBE)
        body.scale.x = 0.34
        body.scale.y = 0.22
        body.scale.z = 0.12
        self.color(body, 0.05, 0.55, 0.95)
        markers.append(body)

        for marker_id, yaw in ((1, math.pi / 4.0), (2, -math.pi / 4.0)):
            arm = self.base_marker(marker_id, Marker.CUBE)
            arm.scale.x = 0.74
            arm.scale.y = 0.035
            arm.scale.z = 0.035
            arm.pose.orientation.z = math.sin(yaw / 2.0)
            arm.pose.orientation.w = math.cos(yaw / 2.0)
            self.color(arm, 0.75, 0.80, 0.86)
            markers.append(arm)

        rotor_offsets = (
            (0.26, 0.26),
            (0.26, -0.26),
            (-0.26, 0.26),
            (-0.26, -0.26),
        )
        for index, (x_position, y_position) in enumerate(rotor_offsets, start=3):
            rotor = self.base_marker(index, Marker.CYLINDER)
            rotor.pose.position.x = x_position
            rotor.pose.position.y = y_position
            rotor.pose.position.z = 0.03
            rotor.scale.x = 0.19
            rotor.scale.y = 0.19
            rotor.scale.z = 0.025
            self.color(rotor, 0.10, 0.12, 0.14, 0.9)
            markers.append(rotor)

        heading = self.base_marker(7, Marker.ARROW)
        heading.points = [Point(x=0.05), Point(x=0.55)]
        heading.scale.x = 0.045
        heading.scale.y = 0.09
        heading.scale.z = 0.09
        self.color(heading, 0.95, 0.25, 0.12)
        markers.append(heading)

        label = self.base_marker(8, Marker.TEXT_VIEW_FACING)
        label.pose.position.z = 0.42
        label.scale.z = 0.22
        label.text = "UAV0"
        self.color(label, 1.0, 1.0, 1.0)
        markers.append(label)

        return MarkerArray(markers=markers)

    def publish_markers(self, _event):
        self.marker_publisher.publish(self.build_markers())

    def odom_callback(self, message):
        position = message.pose.pose.position
        if self.last_path_point is not None:
            dx = position.x - self.last_path_point.x
            dy = position.y - self.last_path_point.y
            dz = position.z - self.last_path_point.z
            if math.sqrt(dx * dx + dy * dy + dz * dz) < self.path_min_step:
                return

        pose = PoseStamped()
        pose.header = copy.deepcopy(message.header)
        pose.header.frame_id = self.world_frame
        pose.pose = copy.deepcopy(message.pose.pose)
        self.path.header.stamp = message.header.stamp
        self.path.poses.append(pose)
        if len(self.path.poses) > self.max_path_points:
            self.path.poses = self.path.poses[-self.max_path_points :]
        self.last_path_point = copy.deepcopy(position)
        self.path_publisher.publish(self.path)


def main():
    rospy.init_node("ruins_uav_visualizer")
    UavVisualizer()
    rospy.spin()


if __name__ == "__main__":
    main()
