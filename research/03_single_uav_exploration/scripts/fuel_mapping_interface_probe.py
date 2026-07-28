#!/usr/bin/env python3
"""Record FUEL mapping inputs during a short read-only ROS runtime audit."""

import argparse
import json
from pathlib import Path


def message_summary(message, message_type):
    """Build a JSON-safe summary without retaining a point-cloud payload."""
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    summary = {
        "message_type": message_type,
        "frame_id": getattr(header, "frame_id", "").lstrip("/"),
        "stamp": {"secs": getattr(stamp, "secs", None), "nsecs": getattr(stamp, "nsecs", None)},
    }
    if hasattr(message, "width") and hasattr(message, "height"):
        summary["points"] = int(message.width) * int(message.height)
        summary["width"] = int(message.width)
        summary["height"] = int(message.height)
        summary["fields"] = [field.name for field in message.fields]
    return summary


class RuntimeInterfaceProbe:
    def __init__(self, rospy, point_cloud_type, pose_type, odometry_type, arguments):
        self.rospy = rospy
        self.arguments = arguments
        self.first_messages = {}
        self.subscribers = [
            rospy.Subscriber(arguments.cloud_topic, point_cloud_type,
                             lambda msg: self.record("cloud", msg, "sensor_msgs/PointCloud2"), queue_size=1),
            rospy.Subscriber(arguments.sensor_pose_topic, pose_type,
                             lambda msg: self.record("sensor_pose", msg, "geometry_msgs/PoseStamped"), queue_size=1),
            rospy.Subscriber(arguments.odom_topic, odometry_type,
                             lambda msg: self.record("odometry", msg, "nav_msgs/Odometry"), queue_size=1),
        ]

    def record(self, label, message, message_type):
        if label not in self.first_messages:
            self.first_messages[label] = message_summary(message, message_type)
            self.rospy.loginfo("Captured %s: frame=%s", label, self.first_messages[label]["frame_id"])

    def complete(self):
        return all(label in self.first_messages for label in ("cloud", "sensor_pose", "odometry"))

    def payload(self):
        return {
            "schema_version": 1,
            "mode": "read_only_runtime_interface_audit",
            "topics": {
                "cloud": self.arguments.cloud_topic,
                "sensor_pose": self.arguments.sensor_pose_topic,
                "odometry": self.arguments.odom_topic,
            },
            "received": self.first_messages,
            "passed": self.complete(),
            "interpretation": (
                "This audit records message frames only. It does not publish a goal, trajectory, map, TF transform, or planner parameter. "
                "A mapper may be connected only after the cloud frame and pose/odometry relationship are reviewed."
            ),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud-topic", default="/pcl_render_node/cloud")
    parser.add_argument("--sensor-pose-topic", default="/pcl_render_node/sensor_pose")
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.timeout_s <= 0.0:
        parser.error("--timeout-s must be positive")

    import rospy
    from geometry_msgs.msg import PoseStamped
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import PointCloud2

    rospy.init_node("fuel_mapping_interface_probe", anonymous=True)
    probe = RuntimeInterfaceProbe(rospy, PointCloud2, PoseStamped, Odometry, arguments)
    deadline = rospy.Time.now() + rospy.Duration(arguments.timeout_s)
    rate = rospy.Rate(20)
    while not rospy.is_shutdown() and rospy.Time.now() < deadline and not probe.complete():
        rate.sleep()
    payload = probe.payload()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit("FUEL mapping interface audit incomplete; do not connect a mapper yet.")


if __name__ == "__main__":
    main()
