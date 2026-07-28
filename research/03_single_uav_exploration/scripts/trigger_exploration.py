#!/usr/bin/env python3
"""Publish a position-neutral FUEL start signal after odometry is available."""

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
        self.publisher = rospy.Publisher(self.goal_topic, PoseStamped, queue_size=1, latch=True)
        self.subscriber = rospy.Subscriber(self.odom_topic, Odometry, self.odometry_callback, queue_size=1)

    def odometry_callback(self, message):
        self.odometry = message

    def run(self):
        deadline = time.monotonic() + self.timeout_s
        rate = rospy.Rate(20.0)
        while not rospy.is_shutdown() and self.odometry is None:
            if time.monotonic() >= deadline:
                raise RuntimeError("no odometry received from %s within %.1f s" % (self.odom_topic, self.timeout_s))
            rate.sleep()

        rospy.sleep(self.delay_s)
        goal = PoseStamped()
        goal.header.stamp = rospy.Time.now()
        goal.header.frame_id = self.frame_id
        # FUEL uses this message to enter exploration. The measured pose encodes no target.
        goal.pose.position.x = self.odometry.pose.pose.position.x
        goal.pose.position.y = self.odometry.pose.pose.position.y
        goal.pose.position.z = self.odometry.pose.pose.position.z
        goal.pose.orientation = self.odometry.pose.pose.orientation
        self.publisher.publish(goal)
        rospy.loginfo("Published the position-neutral FUEL start signal on %s.", self.goal_topic)
        rospy.sleep(1.0)


def main():
    rospy.init_node("fuel_ruins_automatic_trigger")
    trigger = ExplorationTrigger()
    try:
        trigger.run()
    except RuntimeError as error:
        rospy.logfatal(str(error))
        raise


if __name__ == "__main__":
    main()
