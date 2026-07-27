#!/usr/bin/env python3
"""Compare a saved online occupied cloud with simulator truth after a trial."""

import argparse
import json
import math
from pathlib import Path


def read_ascii_pcd(path):
    points = []
    data_found = False
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if not data_found:
                if stripped == "DATA ascii":
                    data_found = True
                elif stripped.startswith("DATA "):
                    raise ValueError(f"only ASCII PCD is supported: {path}")
                continue
            if not stripped:
                continue
            values = stripped.split()
            if len(values) < 3:
                continue
            point = tuple(float(values[index]) for index in range(3))
            if all(math.isfinite(value) for value in point):
                points.append(point)
    if not data_found:
        raise ValueError(f"missing DATA ascii header: {path}")
    if not points:
        raise ValueError(f"PCD contains no finite XYZ points: {path}")
    return points


def voxelize(points, resolution):
    return {
        tuple(int(round(value / resolution)) for value in point)
        for point in points
    }


def neighbor_offsets(tolerance):
    offsets = []
    limit_squared = tolerance * tolerance
    for x in range(-tolerance, tolerance + 1):
        for y in range(-tolerance, tolerance + 1):
            for z in range(-tolerance, tolerance + 1):
                if x * x + y * y + z * z <= limit_squared:
                    offsets.append((x, y, z))
    return offsets


def matched_count(source, target, offsets):
    return sum(
        any(
            (voxel[0] + offset[0], voxel[1] + offset[1], voxel[2] + offset[2])
            in target
            for offset in offsets
        )
        for voxel in source
    )


def inside_bounds(point, bounds):
    if bounds is None:
        return True
    return all(
        bounds[index] <= point[index] <= bounds[index + 3]
        for index in range(3)
    )


def evaluate(truth_path, observed_path, resolution, tolerance, bounds=None):
    truth_points = [
        point for point in read_ascii_pcd(truth_path)
        if inside_bounds(point, bounds)
    ]
    observed_points = [
        point for point in read_ascii_pcd(observed_path)
        if inside_bounds(point, bounds)
    ]
    if not truth_points:
        raise ValueError("no truth points remain inside the evaluation bounds")
    if not observed_points:
        raise ValueError("no observed points remain inside the evaluation bounds")
    truth = voxelize(truth_points, resolution)
    observed = voxelize(observed_points, resolution)
    offsets = neighbor_offsets(tolerance)
    truth_matched = matched_count(truth, observed, offsets)
    observed_matched = matched_count(observed, truth, offsets)
    recall = truth_matched / len(truth)
    precision = observed_matched / len(observed)
    f1 = (
        0.0
        if precision + recall == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )
    return {
        "schema_version": 1,
        "metric": "occupied_surface_voxel_coverage",
        "important_limit": (
            "Simulator truth is used only after exploration for evaluation. "
            "The metric includes surfaces that may be unobservable, so use it "
            "for controlled comparisons rather than claiming perfect geometry."
        ),
        "resolution_m": resolution,
        "tolerance_voxels": tolerance,
        "evaluation_bounds_m": bounds,
        "truth_pcd": str(truth_path.resolve()),
        "observed_pcd": str(observed_path.resolve()),
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_truth_voxels": truth_matched,
        "matched_observed_voxels": observed_matched,
        "surface_recall": round(recall, 6),
        "surface_precision": round(precision, 6),
        "surface_f1": round(f1, 6),
    }


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth-pcd", required=True, type=Path)
    parser.add_argument("--observed-pcd", required=True, type=Path)
    parser.add_argument("--resolution", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=6,
        metavar=("MIN_X", "MIN_Y", "MIN_Z", "MAX_X", "MAX_Y", "MAX_Z"),
        help="Optional XYZ evaluation volume, applied only after the trial.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    if arguments.resolution <= 0.0:
        raise ValueError("--resolution must be positive")
    if arguments.tolerance_voxels < 0:
        raise ValueError("--tolerance-voxels must be non-negative")
    if arguments.bounds is not None and any(
        arguments.bounds[index] > arguments.bounds[index + 3]
        for index in range(3)
    ):
        raise ValueError("--bounds minimums must not exceed maximums")
    payload = evaluate(
        arguments.truth_pcd,
        arguments.observed_pcd,
        arguments.resolution,
        arguments.tolerance_voxels,
        arguments.bounds,
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
