#!/usr/bin/env python3
"""Derive auditable environment clearance constraints from a passed platform profile."""

from __future__ import print_function

import argparse
import json
import os
import sys


def positive_float(value):
    parsed = float(value)
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert a passed vehicle platform profile into scene geometry limits."
    )
    parser.add_argument("--platform-profile", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--normal-corridor-d", type=positive_float, default=4.0)
    parser.add_argument("--bottleneck-min-d", type=positive_float, default=2.6)
    parser.add_argument("--bottleneck-max-d", type=positive_float, default=3.2)
    parser.add_argument("--turning-zone-d", type=positive_float, default=5.0)
    parser.add_argument("--low-clearance-d", type=positive_float, default=3.0)
    parser.add_argument("--obstacle-gap-d", type=positive_float, default=2.4)
    return parser.parse_args()


def load_json(path):
    with open(path, "r") as stream:
        return json.load(stream)


def write_json(path, value):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    args = parse_args()
    profile = load_json(args.platform_profile)
    if not profile.get("passed"):
        raise SystemExit("platform profile did not pass; correct runtime interface issues first")
    if not profile.get("geometry_ready"):
        raise SystemExit(
            "platform profile has no collision geometry; repeat collection with "
            "--collision-diameter-m and --safety-margin-m"
        )
    vehicle = profile.get("vehicle", {})
    diameter = vehicle.get("effective_planning_diameter_m")
    if not isinstance(diameter, (int, float)) or diameter <= 0.0:
        raise SystemExit("platform profile has no valid effective_planning_diameter_m")
    if args.bottleneck_min_d > args.bottleneck_max_d:
        raise SystemExit("bottleneck minimum cannot exceed bottleneck maximum")

    def metres(multiplier):
        return round(multiplier * diameter, 4)

    constraints = {
        "schema_version": 1,
        "source_platform_profile": os.path.abspath(args.platform_profile),
        "effective_planning_diameter_m": diameter,
        "geometry_rules": {
            "normal_corridor_min_width_m": metres(args.normal_corridor_d),
            "bottleneck_width_range_m": [metres(args.bottleneck_min_d), metres(args.bottleneck_max_d)],
            "turning_or_observation_zone_min_diameter_m": metres(args.turning_zone_d),
            "low_clearance_min_height_m": metres(args.low_clearance_d),
            "obstacle_gap_min_width_m": metres(args.obstacle_gap_d),
        },
        "validation_rules": [
            "Inflate all collision geometry by the per-side safety margin before testing free-space connectivity.",
            "Every declared traversable route must remain connected after inflation.",
            "Any gap below obstacle_gap_min_width_m is labelled non-traversable, not an accidental route.",
            "The online explorer must not read this file; it is for generator and offline validation only.",
        ],
        "literature_basis": [
            "J1: Chinese Journal of Aeronautics 2021, unknown-map online obstacle avoidance.",
            "J2: Aerospace Science and Technology 2022, closed-loop GPS-denied MAV navigation.",
            "J3/J4: Aerospace Science and Technology 2017/2025, cooperative search and dense unknown-environment coverage.",
        ],
    }
    write_json(args.output, constraints)
    print(json.dumps(constraints, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
