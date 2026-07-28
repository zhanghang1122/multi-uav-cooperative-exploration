#!/usr/bin/env python3
"""Evaluate reconstruction on truth surfaces near the recorded UAV trajectory.

This is an offline diagnostic only. It does not create a route, affect FUEL,
or claim line-of-sight visibility. It separates surfaces near recorded flight
positions from surfaces the UAV did not approach under the chosen sensor range.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def read_ascii_pcd(path, bounds=None):
    points = []
    data_found = False
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if not data_found:
                if stripped == "DATA ascii":
                    data_found = True
                elif stripped.startswith("DATA "):
                    raise ValueError("only ASCII PCD is supported")
                continue
            if not stripped:
                continue
            values = stripped.split()
            point = tuple(float(values[index]) for index in range(3))
            if not all(math.isfinite(value) for value in point):
                continue
            if bounds is not None and not all(
                bounds[index] <= point[index] <= bounds[index + 3]
                for index in range(3)
            ):
                continue
            points.append(point)
    if not data_found or not points:
        raise ValueError("PCD contains no valid points")
    return points


def voxelize(points, resolution):
    return {tuple(int(round(value / resolution)) for value in point) for point in points}


def neighbor_offsets(tolerance):
    return [
        (x_value, y_value, z_value)
        for x_value in range(-tolerance, tolerance + 1)
        for y_value in range(-tolerance, tolerance + 1)
        for z_value in range(-tolerance, tolerance + 1)
        if x_value * x_value + y_value * y_value + z_value * z_value <= tolerance * tolerance
    ]


def read_trajectory(path, sample_interval_s):
    poses = []
    previous_time = -math.inf
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            elapsed = float(row["elapsed_s"])
            if elapsed - previous_time < sample_interval_s:
                continue
            poses.append((float(row["x_m"]), float(row["y_m"]), float(row["z_m"])))
            previous_time = elapsed
    if not poses:
        raise ValueError("trajectory contains no sampled poses")
    return poses


def exposed_truth_voxels(truth, poses, resolution, sensor_range_m):
    range_voxels = sensor_range_m / resolution
    bucket_size = max(1, int(math.ceil(range_voxels)))
    buckets = defaultdict(list)
    for voxel in truth:
        key = tuple(int(math.floor(value / bucket_size)) for value in voxel)
        buckets[key].append(voxel)
    radius = int(math.ceil(range_voxels / bucket_size))
    exposed = set()
    limit_squared = range_voxels * range_voxels
    for position in poses:
        center = tuple(int(round(value / resolution)) for value in position)
        center_bucket = tuple(int(math.floor(value / bucket_size)) for value in center)
        for delta_x in range(-radius, radius + 1):
            for delta_y in range(-radius, radius + 1):
                for delta_z in range(-radius, radius + 1):
                    for voxel in buckets.get(
                        (
                            center_bucket[0] + delta_x,
                            center_bucket[1] + delta_y,
                            center_bucket[2] + delta_z,
                        ),
                        (),
                    ):
                        squared_distance = sum(
                            (voxel[index] - center[index]) ** 2 for index in range(3)
                        )
                        if squared_distance <= limit_squared:
                            exposed.add(voxel)
    return exposed


def line_of_sight_clear(start, target, occupied):
    """Coarse voxel ray check; the target surface itself is not a blocker."""
    delta = tuple(target[index] - start[index] for index in range(3))
    steps = max(abs(value) for value in delta)
    if steps <= 1:
        return True
    for step in range(1, steps):
        ratio = step / steps
        voxel = tuple(
            int(round(start[index] + delta[index] * ratio))
            for index in range(3)
        )
        if voxel in occupied:
            return False
    return True


def line_of_sight_truth_voxels(truth, poses, resolution, sensor_range_m):
    range_voxels = sensor_range_m / resolution
    bucket_size = max(1, int(math.ceil(range_voxels)))
    buckets = defaultdict(list)
    for voxel in truth:
        key = tuple(int(math.floor(value / bucket_size)) for value in voxel)
        buckets[key].append(voxel)
    radius = int(math.ceil(range_voxels / bucket_size))
    limit_squared = range_voxels * range_voxels
    visible = set()
    for position in poses:
        center = tuple(int(round(value / resolution)) for value in position)
        center_bucket = tuple(int(math.floor(value / bucket_size)) for value in center)
        for delta_x in range(-radius, radius + 1):
            for delta_y in range(-radius, radius + 1):
                for delta_z in range(-radius, radius + 1):
                    key = (
                        center_bucket[0] + delta_x,
                        center_bucket[1] + delta_y,
                        center_bucket[2] + delta_z,
                    )
                    for voxel in buckets.get(key, ()):
                        if voxel in visible:
                            continue
                        squared_distance = sum(
                            (voxel[index] - center[index]) ** 2
                            for index in range(3)
                        )
                        if (
                            squared_distance <= limit_squared
                            and line_of_sight_clear(center, voxel, truth)
                        ):
                            visible.add(voxel)
    return visible


def match_count(source, target, offsets):
    return sum(
        any(
            (voxel[0] + offset[0], voxel[1] + offset[1], voxel[2] + offset[2]) in target
            for offset in offsets
        )
        for voxel in source
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth-pcd", required=True, type=Path)
    parser.add_argument("--observed-pcd", required=True, type=Path)
    parser.add_argument("--trajectory-csv", required=True, type=Path)
    parser.add_argument("--sensor-range-m", required=True, type=float)
    parser.add_argument("--resolution", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument("--trajectory-sample-interval-s", type=float, default=2.0)
    parser.add_argument("--bounds", nargs=6, type=float)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if min(arguments.sensor_range_m, arguments.resolution, arguments.trajectory_sample_interval_s) <= 0:
        raise ValueError("range, resolution, and sampling interval must be positive")

    truth = voxelize(read_ascii_pcd(arguments.truth_pcd, arguments.bounds), arguments.resolution)
    observed = voxelize(read_ascii_pcd(arguments.observed_pcd, arguments.bounds), arguments.resolution)
    poses = read_trajectory(arguments.trajectory_csv, arguments.trajectory_sample_interval_s)
    exposed = exposed_truth_voxels(truth, poses, arguments.resolution, arguments.sensor_range_m)
    visible = line_of_sight_truth_voxels(
        truth, poses, arguments.resolution, arguments.sensor_range_m
    )
    offsets = neighbor_offsets(arguments.tolerance_voxels)
    matched_exposed = match_count(exposed, observed, offsets)
    matched_visible = match_count(visible, observed, offsets)
    payload = {
        "schema_version": 1,
        "metric": "trajectory_conditioned_range_exposure",
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "range_exposed_truth_voxels": len(exposed),
        "range_exposure_ratio": round(len(exposed) / len(truth), 6),
        "matched_range_exposed_truth_voxels": matched_exposed,
        "range_exposed_surface_recall": round(matched_exposed / len(exposed), 6) if exposed else 0.0,
        "line_of_sight_visible_truth_voxels": len(visible),
        "line_of_sight_exposure_ratio": round(len(visible) / len(truth), 6),
        "matched_line_of_sight_visible_truth_voxels": matched_visible,
        "line_of_sight_visible_surface_recall": (
            round(matched_visible / len(visible), 6) if visible else 0.0
        ),
        "sensor_range_m": arguments.sensor_range_m,
        "trajectory_samples": len(poses),
        "trajectory_sample_interval_s": arguments.trajectory_sample_interval_s,
        "important_limit": (
            "Offline proxy only. The line-of-sight test uses sparse truth voxels and "
            "does not model field of view, sensor noise, or reachable free space. "
            "It never enters planning."
        ),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
