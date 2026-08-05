#!/usr/bin/env python3
"""Read-only G1 audit for the reachability gate R.

This program is deliberately not a planner and does not publish a goal,
trajectory, frontier, occupancy map, or parameter.  During a live FUEL run it
uses only the online occupancy cloud and current odometry to prove two local
gate decisions:

1. an automatically selected point lying on an *observed* obstacle is rejected;
2. a distinct locally clear point with a collision-free path through the
   observed map is selected as the next eligible candidate.

The result is a component-level audit of the safety/reachability gate required
by Protocol V2.1.  It neither changes stock FUEL nor claims to be a completed
frontier allocator.  Its alternative candidate passes a local clearance check
against the currently observed occupancy; it is never presented as a proof of
global free-space reachability.
"""

from __future__ import print_function

import argparse
import json
import math
import os
import time

import rospy
from nav_msgs.msg import Odometry
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def cell_of(x, y, resolution_m):
    return (int(math.floor(x / resolution_m)), int(math.floor(y / resolution_m)))


def cell_center(cell, resolution_m):
    return ((cell[0] + 0.5) * resolution_m, (cell[1] + 0.5) * resolution_m)


def bresenham(start, end):
    """Yield integer grid cells crossed by a two-dimensional line."""
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            return
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += step_x
        if twice_error <= dx:
            error += dx
            y0 += step_y


def clearance_cells(cell, occupied, inflation_cells):
    for dx in range(-inflation_cells, inflation_cells + 1):
        for dy in range(-inflation_cells, inflation_cells + 1):
            if dx * dx + dy * dy <= inflation_cells * inflation_cells:
                if (cell[0] + dx, cell[1] + dy) in occupied:
                    return False
    return True


class ReachabilityGateAudit(object):
    def __init__(self, args):
        self.args = args
        self.started_unix_s = time.time()
        self.position = None
        self.occupied = set()
        self.obstacle_samples = []
        self.cloud_messages = 0
        self.completed = False
        rospy.Subscriber(args.odom_topic, Odometry, self.on_odometry, queue_size=10)
        rospy.Subscriber(args.occupancy_topic, PointCloud2, self.on_occupancy, queue_size=1)
        rospy.Timer(rospy.Duration(0.5), self.check_ready)
        rospy.loginfo(
            "G1 reachability audit is read-only: waiting for online occupancy on %s and odometry on %s",
            args.occupancy_topic,
            args.odom_topic,
        )

    def on_odometry(self, message):
        point = message.pose.pose.position
        self.position = (point.x, point.y, point.z)

    def on_occupancy(self, message):
        self.cloud_messages += 1
        for x, y, z in point_cloud2.read_points(message, field_names=("x", "y", "z"), skip_nans=True):
            # Only project obstacles which overlap the prescribed flight band.
            if z < self.args.flight_min_z_m or z > self.args.flight_max_z_m:
                continue
            cell = cell_of(x, y, self.args.grid_resolution_m)
            self.occupied.add(cell)
            if self.position is not None:
                distance = math.hypot(x - self.position[0], y - self.position[1])
                if (
                    self.args.obstacle_candidate_min_distance_m <= distance
                    <= self.args.obstacle_candidate_max_distance_m
                    and len(self.obstacle_samples) < self.args.max_obstacle_samples
                ):
                    self.obstacle_samples.append((x, y, z))

    def check_ready(self, _event):
        if self.completed:
            return
        if time.time() - self.started_unix_s >= self.args.input_timeout_s:
            self.completed = True
            os.makedirs(os.path.dirname(os.path.abspath(self.args.output)), exist_ok=True)
            write_json(self.args.output, self.missing_input_report())
            rospy.logerr("G1 reachability audit timed out waiting for live inputs: %s", self.args.output)
            rospy.signal_shutdown("G1 audit input timeout")
            return
        if self.position is None or len(self.occupied) < self.args.min_occupied_cells:
            return
        self.completed = True
        report = self.evaluate()
        os.makedirs(os.path.dirname(os.path.abspath(self.args.output)), exist_ok=True)
        write_json(self.args.output, report)
        if report["passed"]:
            rospy.loginfo("G1 reachability gate audit passed: %s", self.args.output)
            rospy.signal_shutdown("G1 audit completed")
        else:
            rospy.logerr("G1 reachability gate audit did not pass: %s", self.args.output)
            rospy.signal_shutdown("G1 audit did not pass")

    def missing_input_report(self):
        return {
            "schema_version": 1,
            "mode": "read_only_component_gate_audit",
            "passed": False,
            "inputs": {
                "occupancy_topic": self.args.occupancy_topic,
                "odometry_topic": self.args.odom_topic,
                "truth_map_usage": "none",
                "route_or_goal_prior_used": False,
                "room_or_scene_labels_used": False,
            },
            "map_snapshot": {
                "cloud_messages_received": self.cloud_messages,
                "projected_occupied_cells": len(self.occupied),
                "input_timeout_s": self.args.input_timeout_s,
            },
            "events": [{
                "event": "input_timeout",
                "reason": "live_odometry_or_sufficient_online_occupancy_was_not_received",
            }],
            "interpretation": (
                "The G1 component gate was not evaluated because the required live FUEL inputs "
                "were absent or incomplete. No candidate, route or map was published."
            ),
            "recorded_unix_s": time.time(),
        }

    def choose_observed_obstacle(self):
        px, py, _pz = self.position
        candidates = []
        for sample in self.obstacle_samples:
            distance = math.hypot(sample[0] - px, sample[1] - py)
            if self.args.obstacle_candidate_min_distance_m <= distance <= self.args.obstacle_candidate_max_distance_m:
                candidates.append((distance, sample))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def choose_local_eligible_candidate(self, start_cell, inflation_cells):
        best = None
        for radius_m in self.args.candidate_radii_m:
            for index in range(self.args.candidate_angle_count):
                angle = 2.0 * math.pi * index / self.args.candidate_angle_count
                x = self.position[0] + radius_m * math.cos(angle)
                y = self.position[1] + radius_m * math.sin(angle)
                candidate_cell = cell_of(x, y, self.args.grid_resolution_m)
                if not clearance_cells(candidate_cell, self.occupied, inflation_cells):
                    continue
                path = list(bresenham(start_cell, candidate_cell))
                if not all(clearance_cells(cell, self.occupied, inflation_cells) for cell in path):
                    continue
                # Prefer a longer local path only after it is proven clear;
                # this makes the second selection distinct from the start cell.
                score = (radius_m, -len(path))
                if best is None or score > best[0]:
                    best = (score, x, y, candidate_cell, len(path))
        return best

    def evaluate(self):
        start_cell = cell_of(self.position[0], self.position[1], self.args.grid_resolution_m)
        inflation_cells = max(1, int(math.ceil(self.args.clearance_radius_m / self.args.grid_resolution_m)))
        events = []
        obstacle_candidate = self.choose_observed_obstacle()
        rejected = False
        if obstacle_candidate is not None:
            obstacle_cell = cell_of(obstacle_candidate[0], obstacle_candidate[1], self.args.grid_resolution_m)
            rejected = not clearance_cells(obstacle_cell, self.occupied, inflation_cells)
            events.append({
                "candidate_id": "audit_observed_obstacle",
                "candidate_xyz_m": [round(value, 3) for value in obstacle_candidate],
                "event": "rejected" if rejected else "unexpectedly_eligible",
                "reason": "observed_occupied_or_inside_inflated_clearance",
            })
        else:
            events.append({
                "candidate_id": "audit_observed_obstacle",
                "event": "not_tested",
                "reason": "no_online_obstacle_sample_in_audited_distance_band",
            })

        next_candidate = self.choose_local_eligible_candidate(start_cell, inflation_cells)
        selected = next_candidate is not None
        if selected:
            _score, x, y, candidate_cell, path_cells = next_candidate
            events.append({
                "candidate_id": "audit_local_clear_candidate",
                "candidate_xyz_m": [round(x, 3), round(y, 3), round(self.position[2], 3)],
                "event": "eligible_selected",
                "reason": "collision_free_in_observed_projected_map",
                "grid_path_cells": path_cells,
                "grid_cell": list(candidate_cell),
            })
        else:
            events.append({
                "candidate_id": "audit_local_clear_candidate",
                "event": "not_selected",
                "reason": "no_collision_free_local_candidate_in_observed_projected_map",
            })

        return {
            "schema_version": 1,
            "mode": "read_only_component_gate_audit",
            "passed": bool(rejected and selected),
            "inputs": {
                "occupancy_topic": self.args.occupancy_topic,
                "odometry_topic": self.args.odom_topic,
                "truth_map_usage": "none",
                "route_or_goal_prior_used": False,
                "room_or_scene_labels_used": False,
            },
            "map_snapshot": {
                "cloud_messages_received": self.cloud_messages,
                "projected_occupied_cells": len(self.occupied),
                "grid_resolution_m": self.args.grid_resolution_m,
                "clearance_radius_m": self.args.clearance_radius_m,
                "flight_band_m": [self.args.flight_min_z_m, self.args.flight_max_z_m],
            },
            "current_pose_xyz_m": [round(value, 3) for value in self.position],
            "events": events,
            "interpretation": (
                "This audit proves only that R can reject an observed occupied candidate and select "
                "a distinct collision-free local candidate from the same online map. It does not "
                "publish either candidate to FUEL, alter stock FUEL, prove global reachability, "
                "or substitute for the later integrated R and multi-UAV experiments."
            ),
            "recorded_unix_s": time.time(),
        }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occupancy-topic", default="/sdf_map/occupancy_all")
    parser.add_argument("--odom-topic", default="/state_ukf/odom")
    parser.add_argument("--output", required=True)
    parser.add_argument("--grid-resolution-m", type=float, default=0.20)
    parser.add_argument("--clearance-radius-m", type=float, default=0.45)
    parser.add_argument("--flight-min-z-m", type=float, default=0.80)
    parser.add_argument("--flight-max-z-m", type=float, default=2.05)
    parser.add_argument("--min-occupied-cells", type=int, default=80)
    parser.add_argument("--max-obstacle-samples", type=int, default=30000)
    parser.add_argument("--obstacle-candidate-min-distance-m", type=float, default=1.0)
    parser.add_argument("--obstacle-candidate-max-distance-m", type=float, default=8.0)
    parser.add_argument("--candidate-radii-m", type=float, nargs="+", default=[1.5, 2.0, 2.5, 3.0])
    parser.add_argument("--candidate-angle-count", type=int, default=36)
    parser.add_argument("--input-timeout-s", type=float, default=90.0)
    return parser.parse_args(rospy.myargv()[1:])


def main():
    rospy.init_node("g1_reachability_gate_audit")
    ReachabilityGateAudit(parse_args())
    rospy.spin()


if __name__ == "__main__":
    main()
