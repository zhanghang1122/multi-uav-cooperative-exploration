#!/usr/bin/env python3
"""Project FUEL depth images into TF-correct local point clouds.

This adapter is deliberately independent of FUEL's planner. It subscribes only
to FUEL's rendered depth and sensor pose, broadcasts their matching transform,
and publishes a sensor-frame cloud for OctoMap.
"""

import copy
import math
import struct


def image_to_depth(message, depth_scale):
    """Decode 32FC1 or 16UC1 ROS depth images into metres without NumPy."""
    encoding = message.encoding.upper()
    if encoding == "32FC1":
        format_code = ">f" if message.is_bigendian else "<f"
        item_size, scale = 4, 1.0
    elif encoding in ("16UC1", "MONO16"):
        format_code = ">H" if message.is_bigendian else "<H"
        item_size, scale = 2, 1.0 / depth_scale
    else:
        raise ValueError("unsupported depth encoding: %s" % message.encoding)
    row_width = message.step // item_size
    if row_width < message.width:
        raise ValueError("depth image step is smaller than width")
    expected = message.height * message.step
    if len(message.data) < expected:
        raise ValueError("depth image payload is shorter than declared dimensions")
    return [
        [
            struct.unpack_from(format_code, message.data, row * message.step + column * item_size)[0] * scale
            for column in range(message.width)
        ]
        for row in range(message.height)
    ]


def project_depth(depth, fx, fy, cx, cy, pixel_stride, min_depth, max_depth):
    """Project valid depth pixels to camera-frame XYZ tuples."""
    if pixel_stride < 1:
        raise ValueError("pixel_stride must be at least one")
    points = []
    for v in range(0, len(depth), pixel_stride):
        for u in range(0, len(depth[v]), pixel_stride):
            z = depth[v][u]
            if math.isfinite(z) and min_depth <= z <= max_depth:
                points.append(((u - cx) * z / fx, (v - cy) * z / fy, z))
    return points


class FuelDepthToCloud:
    def __init__(self, rospy, point_cloud2, point_cloud_type, image_type, pose_type, transform_type, broadcaster, arguments):
        self.rospy = rospy
        self.point_cloud2 = point_cloud2
        self.arguments = arguments
        self.transform_type = transform_type
        self.broadcaster = broadcaster
        self.latest_pose = None
        self.depth_messages = 0
        self.published_clouds = 0
        self.publisher = rospy.Publisher(arguments.output_cloud_topic, point_cloud_type, queue_size=2)
        self.pose_subscriber = rospy.Subscriber(arguments.sensor_pose_topic, pose_type, self.pose_callback, queue_size=5)
        self.depth_subscriber = rospy.Subscriber(arguments.depth_topic, image_type, self.depth_callback, queue_size=2)
        rospy.loginfo("FUEL depth mapper: %s + %s -> %s", arguments.depth_topic, arguments.sensor_pose_topic, arguments.output_cloud_topic)

    def pose_callback(self, message):
        self.latest_pose = message

    def depth_callback(self, message):
        self.depth_messages += 1
        if self.depth_messages % self.arguments.publish_every_n != 0:
            return
        pose = self.latest_pose
        if pose is None:
            self.reject("no sensor pose yet")
            return
        age = abs((message.header.stamp - pose.header.stamp).to_sec())
        if age > self.arguments.max_pose_age_s:
            self.reject("depth/pose stamp gap %.3fs exceeds %.3fs" % (age, self.arguments.max_pose_age_s))
            return
        try:
            depth = image_to_depth(message, self.arguments.depth_scale)
            points = project_depth(depth, self.arguments.fx, self.arguments.fy, self.arguments.cx, self.arguments.cy,
                                   self.arguments.pixel_stride, self.arguments.min_depth_m, self.arguments.max_depth_m)
        except ValueError as error:
            self.reject(str(error))
            return
        if not points:
            self.reject("no valid depth points")
            return
        sensor_frame = message.header.frame_id.lstrip("/") or self.arguments.sensor_frame
        parent_frame = pose.header.frame_id.lstrip("/") or self.arguments.map_frame
        transform = self.transform_type()
        transform.header.stamp = message.header.stamp
        transform.header.frame_id = parent_frame
        transform.child_frame_id = sensor_frame
        transform.transform.translation.x = pose.pose.position.x
        transform.transform.translation.y = pose.pose.position.y
        transform.transform.translation.z = pose.pose.position.z
        transform.transform.rotation = pose.pose.orientation
        self.broadcaster.sendTransform(transform)

        header = copy.copy(message.header)
        header.frame_id = sensor_frame
        self.publisher.publish(self.point_cloud2.create_cloud_xyz32(header, points))
        self.published_clouds += 1
        self.rospy.loginfo_throttle(5.0, "FUEL depth mapper published %d clouds; latest=%d points, frame=%s", self.published_clouds, len(points), sensor_frame)

    def reject(self, reason):
        self.rospy.logwarn_throttle(3.0, "FUEL depth mapper rejected depth: %s", reason)


def main():
    import argparse
    import rospy
    import tf2_ros
    from geometry_msgs.msg import PoseStamped, TransformStamped
    from sensor_msgs import point_cloud2
    from sensor_msgs.msg import Image, PointCloud2

    parser = argparse.ArgumentParser()
    parser.add_argument("--depth-topic", default="/pcl_render_node/depth")
    parser.add_argument("--sensor-pose-topic", default="/pcl_render_node/sensor_pose")
    parser.add_argument("--output-cloud-topic", default="/ruins_global_mapping/depth_cloud_sensor")
    parser.add_argument("--map-frame", default="map")
    parser.add_argument("--sensor-frame", default="SQ01s/camera")
    parser.add_argument("--fx", type=float, default=387.229248046875)
    parser.add_argument("--fy", type=float, default=387.229248046875)
    parser.add_argument("--cx", type=float, default=321.04638671875)
    parser.add_argument("--cy", type=float, default=243.44969177246094)
    parser.add_argument("--pixel-stride", type=int, default=6)
    parser.add_argument("--publish-every-n", type=int, default=3)
    parser.add_argument("--min-depth-m", type=float, default=0.2)
    parser.add_argument("--max-depth-m", type=float, default=5.0)
    parser.add_argument("--depth-scale", type=float, default=1000.0)
    parser.add_argument("--max-pose-age-s", type=float, default=0.15)
    arguments = parser.parse_args()
    if arguments.fx <= 0 or arguments.fy <= 0 or arguments.pixel_stride < 1 or arguments.publish_every_n < 1:
        parser.error("camera focal lengths and sampling parameters must be positive")

    rospy.init_node("fuel_depth_to_cloud")
    FuelDepthToCloud(rospy, point_cloud2, PointCloud2, Image, PoseStamped, TransformStamped,
                     tf2_ros.TransformBroadcaster(), arguments)
    rospy.spin()


if __name__ == "__main__":
    main()
