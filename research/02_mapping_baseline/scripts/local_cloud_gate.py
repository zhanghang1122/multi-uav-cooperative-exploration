#!/usr/bin/env python3
"""Expose only the simulated local cloud to the online mapper."""

import rospy
from sensor_msgs.msg import PointCloud2


class LocalCloudGate:
    def __init__(self):
        input_topic = rospy.get_param(
            "~input_topic", "/quad0_pcl_render_node/sensor_cloud"
        )
        output_topic = rospy.get_param("~output_topic", "/mapping/input_cloud")
        self.expected_frame = rospy.get_param("~expected_frame", "sensor").lstrip("/")
        self.publisher = rospy.Publisher(output_topic, PointCloud2, queue_size=3)
        self.received = 0
        self.rejected = 0
        self.subscriber = rospy.Subscriber(
            input_topic, PointCloud2, self.cloud_callback, queue_size=3
        )
        rospy.loginfo(
            "Local-cloud gate: %s -> %s; expected frame=%s",
            input_topic,
            output_topic,
            self.expected_frame,
        )

    def cloud_callback(self, message):
        frame = message.header.frame_id.lstrip("/")
        if frame != self.expected_frame:
            self.rejected += 1
            rospy.logerr_throttle(
                2.0,
                "Rejecting local cloud in frame '%s'; expected '%s'.",
                frame,
                self.expected_frame,
            )
            return
        if message.width * message.height == 0:
            self.rejected += 1
            rospy.logwarn_throttle(2.0, "Rejecting empty local cloud.")
            return
        # MARSIM ubuntu20 publishes "/sensor". tf2 requires frame IDs without
        # a leading slash, so normalize the validated message before forwarding.
        message.header.frame_id = self.expected_frame
        self.received += 1
        self.publisher.publish(message)
        rospy.loginfo_throttle(
            5.0,
            "Forwarded %d local clouds; latest points=%d.",
            self.received,
            message.width * message.height,
        )


def main():
    rospy.init_node("local_cloud_gate")
    LocalCloudGate()
    rospy.spin()


if __name__ == "__main__":
    main()
