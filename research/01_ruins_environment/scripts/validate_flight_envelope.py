#!/usr/bin/env python3
"""Audit a recorded UAV trajectory against a declared indoor flight envelope.

This is offline only.  It reads the recorder's CSV after a trial ends and
never publishes a command, route, goal, map or planner parameter.
"""

from __future__ import print_function

import argparse
import csv
import json
import os


def read_trajectory(path):
    with open(path, "r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise SystemExit("trajectory CSV has no samples: " + path)
    try:
        return [
            {
                "elapsed_s": float(row["elapsed_s"]),
                "x_m": float(row["x_m"]),
                "y_m": float(row["y_m"]),
                "z_m": float(row["z_m"]),
            }
            for row in rows
        ]
    except (KeyError, ValueError) as error:
        raise SystemExit("trajectory CSV has an invalid schema: {}".format(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-csv", required=True)
    parser.add_argument("--min-z-m", type=float, default=0.80)
    parser.add_argument("--max-z-m", type=float, default=2.05)
    parser.add_argument("--tolerance-m", type=float, default=0.02)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.min_z_m < args.max_z_m or args.tolerance_m < 0.0:
        raise SystemExit("invalid flight-envelope bounds or tolerance")

    rows = read_trajectory(args.trajectory_csv)
    lower = args.min_z_m - args.tolerance_m
    upper = args.max_z_m + args.tolerance_m
    violations = [row for row in rows if row["z_m"] < lower or row["z_m"] > upper]
    result = {
        "schema_version": 1,
        "metric": "offline_trajectory_flight_envelope_compliance",
        "trajectory_csv": os.path.abspath(args.trajectory_csv),
        "flight_volume_z_m": [args.min_z_m, args.max_z_m],
        "tolerance_m": args.tolerance_m,
        "samples": len(rows),
        "min_observed_z_m": round(min(row["z_m"] for row in rows), 6),
        "max_observed_z_m": round(max(row["z_m"] for row in rows), 6),
        "violation_samples": len(violations),
        "first_violation": violations[0] if violations else None,
        "passed": not violations,
        "interpretation": "Offline contract check only; it verifies recorded height, not collision-free motion or map quality.",
    }
    parent = os.path.dirname(os.path.abspath(args.output))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
