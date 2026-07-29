#!/usr/bin/env python3
"""Evaluate an independent OctoMap reconstruction against a truth PCD offline.

This script is deliberately offline-only: it reads completed PCD artifacts and
never connects to ROS or any navigation process.  It reports surface Precision,
Recall, and F1 after voxel matching with a stated spatial tolerance.
"""

import argparse
import csv
import json
import math
import os
import sys

# catkin's executable wrappers live beside the installed Python helpers, while
# direct execution uses this source directory. Support both without ROS.
SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
from record_single_uav_trial import voxel_key, voxelize_points


def read_ascii_pcd(path):
    """Read XYZ values from an ASCII PCD with x/y/z as the first three fields."""
    fields = None
    data_seen = False
    points = []
    with open(path, "r", encoding="ascii") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            upper = line.upper()
            if upper.startswith("FIELDS "):
                fields = line.split()[1:]
                continue
            if upper == "DATA ASCII":
                data_seen = True
                continue
            if not data_seen:
                continue
            values = line.split()
            if fields is None or not {"x", "y", "z"}.issubset(fields):
                raise ValueError("PCD is missing x/y/z fields: %s" % path)
            indices = [fields.index(axis) for axis in ("x", "y", "z")]
            if len(values) <= max(indices):
                raise ValueError("malformed PCD point row: %s" % line)
            points.append(tuple(float(values[index]) for index in indices))
    if not data_seen:
        raise ValueError("only ASCII PCD files are supported: %s" % path)
    return points


def in_bounds(point, bounds):
    if bounds is None:
        return True
    return all(bounds[axis] <= point[axis] <= bounds[axis + 3] for axis in range(3))


def neighbor_keys(key, tolerance_voxels):
    for dx in range(-tolerance_voxels, tolerance_voxels + 1):
        for dy in range(-tolerance_voxels, tolerance_voxels + 1):
            for dz in range(-tolerance_voxels, tolerance_voxels + 1):
                yield (key[0] + dx, key[1] + dy, key[2] + dz)


def surface_metrics(truth_points, observed_points, resolution, tolerance_voxels):
    """Calculate voxel-surface Precision/Recall/F1 with symmetric matching."""
    truth = voxelize_points(truth_points, resolution)
    observed = voxelize_points(observed_points, resolution)
    matched_truth = set()
    matched_observed = set()
    for observed_key in observed:
        nearby = [candidate for candidate in neighbor_keys(observed_key, tolerance_voxels) if candidate in truth]
        if nearby:
            matched_observed.add(observed_key)
            matched_truth.add(min(nearby, key=lambda candidate: sum((a - b) ** 2 for a, b in zip(candidate, observed_key))))
    precision = len(matched_observed) / len(observed) if observed else 0.0
    recall = len(matched_truth) / len(truth) if truth else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_truth_voxels": len(matched_truth),
        "matched_observed_voxels": len(matched_observed),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def parse_bounds(values):
    if values is None:
        return None
    if len(values) != 6:
        raise ValueError("bounds requires xmin ymin zmin xmax ymax zmax")
    xmin, ymin, zmin, xmax, ymax, zmax = values
    if xmin >= xmax or ymin >= ymax or zmin >= zmax:
        raise ValueError("bounds minimums must be smaller than maximums")
    return values


def write_snapshot_curve(snapshot_directory, truth_points, resolution, tolerance_voxels, output_path):
    rows = []
    if not snapshot_directory or not os.path.isdir(snapshot_directory):
        return rows
    for name in sorted(item for item in os.listdir(snapshot_directory) if item.endswith(".pcd")):
        elapsed_token = name.rsplit("_", 1)[-1].replace("s.pcd", "")
        elapsed_s = float(elapsed_token) if elapsed_token.isdigit() else float("nan")
        metrics = surface_metrics(truth_points, read_ascii_pcd(os.path.join(snapshot_directory, name)), resolution, tolerance_voxels)
        rows.append((elapsed_s, name, metrics["precision"], metrics["recall"], metrics["f1"], metrics["observed_voxels"]))
    if rows:
        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("elapsed_s", "snapshot_pcd", "precision", "recall", "f1", "observed_voxels"))
            writer.writerows(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--observed-pcd", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--snapshot-dir")
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument("--bounds", type=float, nargs=6)
    arguments = parser.parse_args()
    if arguments.resolution_m <= 0 or arguments.tolerance_voxels < 0:
        parser.error("resolution must be positive and tolerance must be non-negative")
    try:
        bounds = parse_bounds(arguments.bounds)
        truth = [point for point in read_ascii_pcd(arguments.truth_pcd) if in_bounds(point, bounds)]
        observed = [point for point in read_ascii_pcd(arguments.observed_pcd) if in_bounds(point, bounds)]
    except ValueError as error:
        parser.error(str(error))
    metrics = surface_metrics(truth, observed, arguments.resolution_m, arguments.tolerance_voxels)
    metrics.update({
        "schema_version": 1,
        "metric": "offline_voxel_surface_precision_recall_f1",
        "truth_map_usage": "offline_evaluation_only",
        "resolution_m": arguments.resolution_m,
        "tolerance_voxels": arguments.tolerance_voxels,
        "bounds": bounds,
    })
    if arguments.snapshot_dir:
        curve_path = os.path.splitext(arguments.output)[0] + "_curve.csv"
        metrics["snapshot_curve_csv"] = curve_path
        metrics["snapshot_count"] = len(write_snapshot_curve(arguments.snapshot_dir, truth, arguments.resolution_m,
                                                                arguments.tolerance_voxels, curve_path))
    with open(arguments.output, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
