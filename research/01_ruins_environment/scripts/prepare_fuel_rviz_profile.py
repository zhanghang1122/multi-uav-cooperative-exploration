#!/usr/bin/env python3
"""Derive a FUEL RViz profile with the correct Frontier Marker display.

The source is the locally installed FUEL `traj.rviz`, which is already known to
work in the user's ROS/RViz installation.  The generated profile changes only
the Frontier visualization type and fixed frame; it never changes FUEL source
files or publishes to ROS.
"""

from __future__ import print_function

import argparse
import os
import sys

try:
    import yaml
except ImportError:
    raise SystemExit("python3-yaml is required; install it with: sudo apt install python3-yaml")


FRONTIER_TOPIC = "/planning_vis/frontier"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuel-workspace", default=os.path.expanduser("~/fuel_ws"))
    parser.add_argument("--output", default="/tmp/fuel_building_baseline_overlay/fuel_b1_rviz.rviz")
    return parser.parse_args()


def marker_display():
    return {
        "Class": "rviz/Marker",
        "Enabled": True,
        "Marker Topic": FRONTIER_TOPIC,
        "Name": "frontier",
        "Namespaces": {"frontier": True},
        "Queue Size": 100,
        "Value": True,
    }


def is_frontier_display(display):
    if not isinstance(display, dict):
        return False
    name = str(display.get("Name", "")).strip().lower()
    topic = str(display.get("Marker Topic", display.get("Topic", ""))).strip()
    return name == "frontier" or topic == FRONTIER_TOPIC


def replace_frontier(displays):
    """Replace a nested original Frontier display, preserving other FUEL views."""
    replaced = False
    for index, display in enumerate(displays):
        if is_frontier_display(display):
            displays[index] = marker_display()
            replaced = True
            continue
        if isinstance(display, dict) and isinstance(display.get("Displays"), list):
            replaced = replace_frontier(display["Displays"]) or replaced
    return replaced


def main():
    args = parse_args()
    source = os.path.join(
        os.path.abspath(os.path.expanduser(args.fuel_workspace)),
        "src", "FUEL", "fuel_planner", "exploration_manager", "rviz", "traj.rviz",
    )
    if not os.path.isfile(source):
        raise SystemExit("FUEL RViz source profile was not found: " + source)
    with open(source, "r", encoding="utf-8") as stream:
        profile = yaml.safe_load(stream)
    if not isinstance(profile, dict):
        raise SystemExit("FUEL RViz source profile is not a YAML mapping: " + source)

    manager = profile.setdefault("Visualization Manager", {})
    if not isinstance(manager, dict):
        raise SystemExit("FUEL RViz source profile has no Visualization Manager mapping")
    options = manager.setdefault("Global Options", {})
    options["Fixed Frame"] = "world"
    displays = manager.setdefault("Displays", [])
    if not isinstance(displays, list):
        raise SystemExit("FUEL RViz source profile has no Displays list")
    replaced = replace_frontier(displays)
    if not replaced:
        displays.append(marker_display())

    output = os.path.abspath(os.path.expanduser(args.output))
    output_dir = os.path.dirname(output)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    with open(output, "w", encoding="utf-8", newline="\n") as stream:
        yaml.safe_dump(profile, stream, default_flow_style=False, sort_keys=False, width=1000)
    print("Generated RViz profile: {}".format(output))
    print("Source profile: {}".format(source))
    print("Frontier display: rviz/Marker on {}".format(FRONTIER_TOPIC))


if __name__ == "__main__":
    sys.exit(main())
