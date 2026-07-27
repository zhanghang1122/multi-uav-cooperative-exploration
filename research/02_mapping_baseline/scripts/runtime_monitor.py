#!/usr/bin/env python3
"""Record objective evidence that local sensing drives online map growth."""

import json
import os
import time

import rospy
from nav_msgs.msg import Odometry
from octomap_msgs.msg import Octomap
from sensor_msgs.msg import PointCloud2


class TopicStats:
    def __init__(self):
        self.messages = 0
        self.first_time_s = None
        self.last_time_s = None
        self.first_points = None
        self.max_points = 0
        self.frames = set()

    def update(self, start_time, frame=None, points=None):
        elapsed = time.monotonic() - start_time
        self.messages += 1
        if self.first_time_s is None:
            self.first_time_s = elapsed
        self.last_time_s = elapsed
        if frame:
            self.frames.add(frame)
        if points is not None:
            if self.first_points is None:
                self.first_points = points
            self.max_points = max(self.max_points, points)

    def as_dict(self):
        return {
            "messages": self.messages,
            "first_time_s": self._round(self.first_time_s),
            "last_time_s": self._round(self.last_time_s),
            "first_points": self.first_points,
            "max_points": self.max_points,
            "frames": sorted(self.frames),
        }

    @staticmethod
    def _round(value):
        return None if value is None else round(value, 3)


class RuntimeMonitor:
    def __init__(self):
        self.start_time = time.monotonic()
        self.duration = float(rospy.get_param("~duration_s", 90.0))
        self.result_file = rospy.get_param(
            "~result_file", "/tmp/ruins_mapping_runtime.json"
        )
        self.stats = {
            "odometry": TopicStats(),
            "local_cloud": TopicStats(),
            "mapping_input": TopicStats(),
            "truth_cloud": TopicStats(),
            "octomap": TopicStats(),
            "occupied_centers": TopicStats(),
        }
        self.topics = {
            "odometry": rospy.get_param(
                "~odom_topic", "/quad_0/lidar_slam/odom"
            ),
            "local_cloud": rospy.get_param(
                "~local_cloud_topic", "/quad0_pcl_render_node/sensor_cloud"
            ),
            "mapping_input": rospy.get_param(
                "~mapping_cloud_topic", "/mapping/input_cloud"
            ),
            "truth_cloud": rospy.get_param(
                "~truth_cloud_topic", "/map_generator/global_cloud"
            ),
            "octomap": rospy.get_param("~octomap_topic", "/octomap_binary"),
            "occupied_centers": rospy.get_param(
                "~occupied_centers_topic", "/octomap_point_cloud_centers"
            ),
        }
        self.subscribers = [
            rospy.Subscriber(
                self.topics["odometry"],
                Odometry,
                lambda msg: self.odom_callback("odometry", msg),
                queue_size=10,
            ),
            rospy.Subscriber(
                self.topics["local_cloud"],
                PointCloud2,
                lambda msg: self.cloud_callback("local_cloud", msg),
                queue_size=3,
            ),
            rospy.Subscriber(
                self.topics["mapping_input"],
                PointCloud2,
                lambda msg: self.cloud_callback("mapping_input", msg),
                queue_size=3,
            ),
            rospy.Subscriber(
                self.topics["truth_cloud"],
                PointCloud2,
                lambda msg: self.cloud_callback("truth_cloud", msg),
                queue_size=1,
            ),
            rospy.Subscriber(
                self.topics["octomap"],
                Octomap,
                lambda msg: self.octomap_callback("octomap", msg),
                queue_size=3,
            ),
            rospy.Subscriber(
                self.topics["occupied_centers"],
                PointCloud2,
                lambda msg: self.cloud_callback("occupied_centers", msg),
                queue_size=3,
            ),
        ]

    def odom_callback(self, key, message):
        self.stats[key].update(self.start_time, frame=message.header.frame_id)

    def cloud_callback(self, key, message):
        self.stats[key].update(
            self.start_time,
            frame=message.header.frame_id,
            points=message.width * message.height,
        )

    def octomap_callback(self, key, message):
        self.stats[key].update(
            self.start_time, frame=message.header.frame_id, points=len(message.data)
        )

    def result(self):
        checks = {
            "odometry_received": self.stats["odometry"].messages > 0,
            "local_cloud_received": self.stats["local_cloud"].messages > 0,
            "gate_forwarded_local_cloud": self.stats["mapping_input"].messages > 0,
            "local_cloud_uses_sensor_frame": (
                "sensor" in {frame.lstrip("/") for frame in self.stats["local_cloud"].frames}
            ),
            "mapping_input_preserves_sensor_frame": (
                "sensor"
                in {
                    frame.lstrip("/")
                    for frame in self.stats["mapping_input"].frames
                }
            ),
            "octomap_received": self.stats["octomap"].messages > 0,
            "octomap_uses_world_frame": (
                "world" in {frame.lstrip("/") for frame in self.stats["octomap"].frames}
            ),
            "occupied_centers_received": self.stats["occupied_centers"].messages > 0,
            "occupied_map_grew": (
                self.stats["occupied_centers"].first_points is not None
                and self.stats["occupied_centers"].max_points
                > self.stats["occupied_centers"].first_points
            ),
            "mapper_input_is_not_truth_topic": (
                self.topics["mapping_input"] != self.topics["truth_cloud"]
            ),
        }
        return {
            "schema_version": 1,
            "duration_s": round(time.monotonic() - self.start_time, 3),
            "topics": self.topics,
            "statistics": {
                key: value.as_dict() for key, value in self.stats.items()
            },
            "checks": checks,
            "passed": all(checks.values()),
        }

    def write(self):
        payload = self.result()
        directory = os.path.dirname(os.path.abspath(self.result_file))
        os.makedirs(directory, exist_ok=True)
        with open(
            self.result_file, "w", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        if payload["passed"]:
            rospy.loginfo("Mapping runtime validation passed.")
        else:
            failed = [key for key, value in payload["checks"].items() if not value]
            rospy.logerr("Mapping runtime validation failed: %s", ", ".join(failed))
        rospy.loginfo("Runtime report: %s", self.result_file)

    def run(self):
        deadline = time.monotonic() + self.duration
        rate = rospy.Rate(5.0)
        while not rospy.is_shutdown() and time.monotonic() < deadline:
            rate.sleep()
        self.write()


def main():
    rospy.init_node("mapping_runtime_monitor")
    monitor = RuntimeMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
