#!/usr/bin/env python3
"""Start official FUEL exploration with the current pose, never a search goal."""

from __future__ import print_function

import argparse
import sys

import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--goal-topic", default="/move_base_simple/goal")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--delay-s", type=float, default=2.0)
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    rospy.init_node("fuel_position_neutral_trigger", anonymous=False)
    message = rospy.wait_for_message(args.odom_topic, Odometry, timeout=args.timeout_s)
    rospy.sleep(args.delay_s)
    goal = PoseStamped()
    goal.header.stamp = rospy.Time.now()
    goal.header.frame_id = message.header.frame_id or "world"
    goal.pose = message.pose.pose
    publisher = rospy.Publisher(args.goal_topic, PoseStamped, queue_size=1, latch=True)
    rospy.sleep(0.25)
    publisher.publish(goal)
    rospy.loginfo("Published position-neutral FUEL start trigger at current odometry pose; no search goal or route was supplied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
