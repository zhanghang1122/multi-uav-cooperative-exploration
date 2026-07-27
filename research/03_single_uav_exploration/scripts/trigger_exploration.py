#!/usr/bin/env python3
"""Publish one RViz-compatible goal after FUEL odometry becomes available."""

import time

import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry


class ExplorationTrigger:
    def __init__(self):
        self.delay_s = float(rospy.get_param("~delay_s", 5.0))
        self.timeout_s = float(rospy.get_param("~timeout_s", 30.0))
        self.frame_id = rospy.get_param("~frame_id", "world")
        self.odom_topic = rospy.get_param("~odom_topic", "/state_ukf/odom")
        self.goal_topic = rospy.get_param("~goal_topic", "/move_base_simple/goal")
        self.odometry = None
        self.publisher = rospy.Publisher(
            self.goal_topic, PoseStamped, queue_size=1, latch=True
        )
        self.subscriber = rospy.Subscriber(
            self.odom_topic, Odometry, self.odometry_callback, queue_size=1
        )

    def odometry_callback(self, message):
        self.odometry = message

    def run(self):
        deadline = time.monotonic() + self.timeout_s
        rate = rospy.Rate(20.0)
        while not rospy.is_shutdown() and self.odometry is None:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"no odometry received from {self.odom_topic} within "
                    f"{self.timeout_s:.1f} s"
                )
            rate.sleep()

        rospy.sleep(self.delay_s)
        goal = PoseStamped()
        goal.header.stamp = rospy.Time.now()
        goal.header.frame_id = self.frame_id
        goal.pose.position.x = self.odometry.pose.pose.position.x + 1.0
        goal.pose.position.y = self.odometry.pose.pose.position.y
        goal.pose.position.z = max(self.odometry.pose.pose.position.z, 0.5)
        goal.pose.orientation.w = 1.0
        self.publisher.publish(goal)
        rospy.loginfo(
            "Published the one-shot FUEL exploration trigger on %s.",
            self.goal_topic,
        )
        rospy.sleep(1.0)


def main():
    rospy.init_node("fuel_ruins_automatic_trigger")
    trigger = ExplorationTrigger()
    try:
        trigger.run()
    except RuntimeError as exc:
        rospy.logfatal(str(exc))
        raise


if __name__ == "__main__":
    main()
