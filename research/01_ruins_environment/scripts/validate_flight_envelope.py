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
    parser.add_argument(
        "--analysis-start-elapsed-s",
        type=float,
        default=0.0,
        help=(
            "Ignore initialization samples before this recorder-relative time. "
            "For E2 trials this must equal the position-neutral trigger delay (6.0 s)."
        ),
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.min_z_m < args.max_z_m or args.tolerance_m < 0.0 or args.analysis_start_elapsed_s < 0.0:
        raise SystemExit("invalid flight-envelope bounds or tolerance")

    rows = read_trajectory(args.trajectory_csv)
    analysis_rows = [row for row in rows if row["elapsed_s"] >= args.analysis_start_elapsed_s]
    if not analysis_rows:
        raise SystemExit("no trajectory samples remain after the analysis start time")
    lower = args.min_z_m - args.tolerance_m
    upper = args.max_z_m + args.tolerance_m
    violations = [row for row in analysis_rows if row["z_m"] < lower or row["z_m"] > upper]
    lower_violations = [row for row in analysis_rows if row["z_m"] < lower]
    upper_violations = [row for row in analysis_rows if row["z_m"] > upper]
    min_row = min(analysis_rows, key=lambda row: row["z_m"])
    max_row = max(analysis_rows, key=lambda row: row["z_m"])
    result = {
        "schema_version": 2,
        "metric": "offline_trajectory_flight_envelope_compliance",
        "trajectory_csv": os.path.abspath(args.trajectory_csv),
        "flight_volume_z_m": [args.min_z_m, args.max_z_m],
        "tolerance_m": args.tolerance_m,
        "samples": len(analysis_rows),
        "ignored_initialization_samples": len(rows) - len(analysis_rows),
        "analysis_start_elapsed_s": args.analysis_start_elapsed_s,
        "min_observed_z_m": round(min_row["z_m"], 6),
        "max_observed_z_m": round(max_row["z_m"], 6),
        "min_observed_sample": min_row,
        "max_observed_sample": max_row,
        "violation_samples": len(violations),
        "lower_violation_samples": len(lower_violations),
        "upper_violation_samples": len(upper_violations),
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
