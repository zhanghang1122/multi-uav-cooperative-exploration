#!/usr/bin/env python3
"""Fly a declared centerline route for mapping-chain validation only."""

import json
import math
import os
import time

import rospy
from nav_msgs.msg import Odometry
from quadrotor_msgs.msg import PositionCommand


class ReferenceTrajectory:
    def __init__(self):
        self.odom_topic = rospy.get_param(
            "~odom_topic", "/quad_0/lidar_slam/odom"
        )
        self.command_topic = rospy.get_param(
            "~command_topic", "/quad_0/planning/pos_cmd"
        )
        self.rate_hz = float(rospy.get_param("~rate_hz", 20.0))
        self.tolerance = float(rospy.get_param("~position_tolerance_m", 0.35))
        self.hold_time = float(rospy.get_param("~hold_time_s", 1.0))
        self.timeout = float(rospy.get_param("~waypoint_timeout_s", 30.0))
        self.start_delay = float(rospy.get_param("~start_delay_s", 3.0))
        self.position_gain = rospy.get_param("~position_gain", [7.0, 7.0, 6.2])
        self.velocity_gain = rospy.get_param("~velocity_gain", [4.0, 4.0, 4.0])
        self.waypoints = rospy.get_param("~waypoints")
        self.result_file = rospy.get_param(
            "~result_file", "/tmp/ruins_mapping_trajectory.json"
        )
        self.position = None
        self.events = []
        self.publisher = rospy.Publisher(
            self.command_topic, PositionCommand, queue_size=10
        )
        self.subscriber = rospy.Subscriber(
            self.odom_topic, Odometry, self.odom_callback, queue_size=10
        )

    def odom_callback(self, message):
        position = message.pose.pose.position
        self.position = (position.x, position.y, position.z)

    def distance(self, waypoint):
        dx = self.position[0] - float(waypoint["x"])
        dy = self.position[1] - float(waypoint["y"])
        dz = self.position[2] - float(waypoint["z"])
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def make_command(self, waypoint, sequence):
        command = PositionCommand()
        command.header.stamp = rospy.Time.now()
        command.header.frame_id = "world"
        command.position.x = float(waypoint["x"])
        command.position.y = float(waypoint["y"])
        command.position.z = float(waypoint["z"])
        command.yaw = float(waypoint.get("yaw", 0.0))
        command.yaw_dot = 0.0
        command.kx = self.position_gain
        command.kv = self.velocity_gain
        command.trajectory_id = sequence + 1
        command.trajectory_flag = PositionCommand.TRAJECTORY_STATUS_READY
        return command

    def record(self, waypoint, status, elapsed_s):
        event = {
            "name": waypoint["name"],
            "target": [
                float(waypoint["x"]),
                float(waypoint["y"]),
                float(waypoint["z"]),
            ],
            "status": status,
            "elapsed_s": round(elapsed_s, 3),
        }
        if self.position is not None:
            event["final_position"] = [round(value, 3) for value in self.position]
            event["final_error_m"] = round(self.distance(waypoint), 3)
        self.events.append(event)

    def write_result(self, completed):
        directory = os.path.dirname(os.path.abspath(self.result_file))
        os.makedirs(directory, exist_ok=True)
        payload = {
            "schema_version": 1,
            "purpose": "mapping_chain_validation_not_autonomous_exploration",
            "completed": completed,
            "waypoint_count": len(self.waypoints),
            "events": self.events,
        }
        with open(
            self.result_file, "w", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def run(self):
        rospy.loginfo("Waiting for odometry on %s.", self.odom_topic)
        while not rospy.is_shutdown() and self.position is None:
            rospy.sleep(0.1)
        if rospy.is_shutdown():
            return

        rospy.sleep(self.start_delay)
        rate = rospy.Rate(self.rate_hz)
        completed = True

        for sequence, waypoint in enumerate(self.waypoints):
            start = time.monotonic()
            inside_since = None
            command = self.make_command(waypoint, sequence)
            rospy.loginfo("Reference target %s.", waypoint["name"])

            while not rospy.is_shutdown():
                command.header.stamp = rospy.Time.now()
                self.publisher.publish(command)
                error = self.distance(waypoint)
                now = time.monotonic()

                if error <= self.tolerance:
                    if inside_since is None:
                        inside_since = now
                    if now - inside_since >= self.hold_time:
                        self.record(waypoint, "reached", now - start)
                        break
                else:
                    inside_since = None

                if now - start > self.timeout:
                    self.record(waypoint, "timeout", now - start)
                    rospy.logerr(
                        "Reference target %s timed out at %.2f m.",
                        waypoint["name"],
                        error,
                    )
                    completed = False
                    self.write_result(completed)
                    return
                rate.sleep()

        self.write_result(completed)
        rospy.loginfo("Reference trajectory finished: %s.", self.result_file)


def main():
    rospy.init_node("reference_trajectory")
    runner = ReferenceTrajectory()
    runner.run()


if __name__ == "__main__":
    main()
