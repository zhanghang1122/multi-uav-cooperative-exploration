#!/usr/bin/env python3
"""Compute truth-based 3D mapping progress after an exploration trial."""

import argparse
import bisect
import csv
import math
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
                    raise ValueError("only ASCII PCD is supported: {}".format(path))
                continue
            if not stripped:
                continue
            values = stripped.split()
            if len(values) < 3:
                continue
            point = tuple(float(values[index]) for index in range(3))
            if not all(math.isfinite(value) for value in point):
                continue
            if bounds is not None and not all(
                bounds[index] <= point[index] <= bounds[index + 3]
                for index in range(3)
            ):
                continue
            points.append(point)
    if not data_found:
        raise ValueError("missing DATA ascii header: {}".format(path))
    if not points:
        raise ValueError("truth PCD contains no points inside evaluation bounds")
    return points


def voxelize(points, resolution):
    return {
        tuple(int(round(value / resolution)) for value in point)
        for point in points
    }


def neighbor_offsets(tolerance):
    offsets = []
    limit_squared = tolerance * tolerance
    for x_value in range(-tolerance, tolerance + 1):
        for y_value in range(-tolerance, tolerance + 1):
            for z_value in range(-tolerance, tolerance + 1):
                if (
                    x_value * x_value
                    + y_value * y_value
                    + z_value * z_value
                    <= limit_squared
                ):
                    offsets.append((x_value, y_value, z_value))
    return offsets


def read_first_seen(path, bounds, resolution):
    result = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"voxel_x", "voxel_y", "voxel_z", "first_seen_s"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("first-seen CSV has an invalid header")
        for row in reader:
            voxel = (
                int(row["voxel_x"]),
                int(row["voxel_y"]),
                int(row["voxel_z"]),
            )
            point = tuple(value * resolution for value in voxel)
            if bounds is not None and not all(
                bounds[index] <= point[index] <= bounds[index + 3]
                for index in range(3)
            ):
                continue
            first_seen = float(row["first_seen_s"])
            if math.isfinite(first_seen) and first_seen >= 0.0:
                result[voxel] = min(first_seen, result.get(voxel, first_seen))
    if not result:
        raise ValueError("first-seen CSV contains no valid occupied voxels")
    return result


def compute_series(truth, observed_times, tolerance, interval_s):
    offsets = neighbor_offsets(tolerance)
    truth_match_times = []
    for voxel in truth:
        candidates = [
            observed_times.get(
                (
                    voxel[0] + offset[0],
                    voxel[1] + offset[1],
                    voxel[2] + offset[2],
                )
            )
            for offset in offsets
        ]
        candidates = [value for value in candidates if value is not None]
        if candidates:
            truth_match_times.append(min(candidates))
    truth_match_times.sort()

    all_observed_times = sorted(observed_times.values())
    matched_observed_times = sorted(
        first_seen
        for voxel, first_seen in observed_times.items()
        if any(
            (
                voxel[0] + offset[0],
                voxel[1] + offset[1],
                voxel[2] + offset[2],
            )
            in truth
            for offset in offsets
        )
    )
    maximum = max(all_observed_times)
    sample_count = int(math.ceil(maximum / interval_s))
    sample_times = [index * interval_s for index in range(sample_count + 1)]
    if not math.isclose(sample_times[-1], maximum):
        sample_times.append(maximum)

    rows = []
    for elapsed in sample_times:
        observed_count = bisect.bisect_right(all_observed_times, elapsed)
        matched_observed = bisect.bisect_right(matched_observed_times, elapsed)
        matched_truth = bisect.bisect_right(truth_match_times, elapsed)
        recall = matched_truth / len(truth)
        precision = (
            0.0 if observed_count == 0 else matched_observed / observed_count
        )
        f1_score = (
            0.0
            if recall + precision == 0.0
            else 2.0 * recall * precision / (recall + precision)
        )
        rows.append(
            {
                "elapsed_s": elapsed,
                "observed_voxels": observed_count,
                "matched_truth_voxels": matched_truth,
                "surface_recall": recall,
                "surface_precision": precision,
                "surface_f1": f1_score,
            }
        )
    return rows


def write_series(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "elapsed_s",
        "observed_voxels",
        "matched_truth_voxels",
        "surface_recall",
        "surface_precision",
        "surface_f1",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "elapsed_s": f"{row['elapsed_s']:.6f}",
                    "observed_voxels": row["observed_voxels"],
                    "matched_truth_voxels": row["matched_truth_voxels"],
                    "surface_recall": f"{row['surface_recall']:.9f}",
                    "surface_precision": f"{row['surface_precision']:.9f}",
                    "surface_f1": f"{row['surface_f1']:.9f}",
                }
            )


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth-pcd", required=True, type=Path)
    parser.add_argument("--first-seen-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolution", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument("--interval-s", type=float, default=2.0)
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=6,
        metavar=("MIN_X", "MIN_Y", "MIN_Z", "MAX_X", "MAX_Y", "MAX_Z"),
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    if arguments.resolution <= 0.0:
        raise ValueError("--resolution must be positive")
    if arguments.interval_s <= 0.0:
        raise ValueError("--interval-s must be positive")
    if arguments.tolerance_voxels < 0:
        raise ValueError("--tolerance-voxels must be non-negative")
    truth = voxelize(
        read_ascii_pcd(arguments.truth_pcd, arguments.bounds),
        arguments.resolution,
    )
    observed_times = read_first_seen(
        arguments.first_seen_csv,
        arguments.bounds,
        arguments.resolution,
    )
    rows = compute_series(
        truth,
        observed_times,
        arguments.tolerance_voxels,
        arguments.interval_s,
    )
    write_series(arguments.output, rows)
    final = rows[-1]
    print(
        "Coverage series: {} samples, final recall {:.3f}, precision {:.3f}, F1 {:.3f}".format(
            len(rows),
            final["surface_recall"],
            final["surface_precision"],
            final["surface_f1"],
        )
    )


if __name__ == "__main__":
    main()
