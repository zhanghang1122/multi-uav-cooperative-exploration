#!/usr/bin/env python3
"""Start one E2 B1 trial only when no incompatible FUEL session is active.

The command is intentionally conservative: it never kills a process, sends a
goal, or changes planner parameters.  It prevents ROS node-name collisions
between a stale FUEL session and the fixed B1 trial launcher.
"""

from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys
import time


CONFLICTING_NODES = frozenset((
    "/exploration_node",
    "/traj_server",
    "/waypoint_generator",
    "/map_pub",
    "/quadrotor_simulator_so3",
    "/so3_control",
    "/so3_disturbance_generator",
    "/odom_visualization",
    "/pcl_render_node",
    "/ruins_online_map_visual_filter",
    "/ruins_uav_pose_marker",
    "/fuel_b1_rviz",
    "/fuel_b1_trial_recorder",
    "/fuel_position_neutral_trigger",
))


def active_nodes():
    """Return active ROS nodes; no master means that the session is clean."""
    try:
        result = subprocess.run(
            ("rosnode", "list"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scene", default="e2_primary_damaged_interior")
    parser.add_argument("--method-id", default="B1_fuel_frontier_single_uav")
    parser.add_argument("--planner-stall-timeout-s", type=float, default=45.0)
    return parser.parse_args()


def write_launch_record(output_dir, command):
    """Persist the accepted request before replacing this process with roslaunch."""
    output_dir = os.path.abspath(os.path.expanduser(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    record_path = os.path.join(output_dir, "launch_request.json")
    with open(record_path, "w", encoding="utf-8") as stream:
        json.dump({
            "schema_version": 1,
            "accepted": True,
            "recorded_unix_s": time.time(),
            "command": command,
            "interpretation": (
                "This record confirms that the guarded trial launcher accepted the request. "
                "It does not confirm that roslaunch, FUEL, RViz, or the recorder started successfully."
            ),
        }, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return record_path


def main():
    args = parse_args()
    nodes = active_nodes()
    conflicts = sorted(set(nodes or ()).intersection(CONFLICTING_NODES))
    if conflicts:
        print(json.dumps({
            "started": False,
            "reason": "existing_fuel_session",
            "conflicting_nodes": conflicts,
            "action": "Stop the listed stale nodes, then run this command again.",
        }, indent=2, sort_keys=True))
        return 2

    command = [
        "roslaunch",
        "ruins_urban_01",
        "run_e2_b1_trial.launch",
        "overlay_file:={}".format(os.path.abspath(os.path.expanduser(args.overlay_file))),
        "output_dir:={}".format(os.path.abspath(os.path.expanduser(args.output_dir))),
        "scene:={}".format(args.scene),
        "method_id:={}".format(args.method_id),
        "planner_stall_timeout_s:={}".format(args.planner_stall_timeout_s),
    ]
    record_path = write_launch_record(args.output_dir, command)
    print(json.dumps({
        "started": True,
        "existing_ros_master": nodes is not None,
        "launch_record": record_path,
        "runtime_contract": "no_route_no_goal_no_truth_map",
    }, indent=2, sort_keys=True))
    os.execvp(command[0], command)


if __name__ == "__main__":
    sys.exit(main())
