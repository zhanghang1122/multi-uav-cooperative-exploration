#!/usr/bin/env python3
"""Diagnose a completed E2 trial by post-hoc branch-wise surface coverage.

This program is deliberately an offline evaluator.  It reads only a completed
online occupancy PCD, the fixed E2 truth PCD, and an optionally recorded
trajectory.  Its spatial masks are never written into a launch file, ROS
parameter, map, frontier, task allocator, or planner.  The running UAV cannot
observe their names or coordinates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


# These masks follow the physical wings created in generate_e2_primary_benchmark
# (north gallery, south utility wing, east service loop).  They are evaluation
# regions only.  The central hall is intentionally reported separately so that
# a high score near the entrance cannot hide a missed remote wing.
REGIONS = {
    "central_hall": (-14.8, 8.0, -4.0, 4.0, 0.0, 4.2),
    "north_gallery": (-14.8, 8.0, 4.0, 18.0, 0.0, 4.2),
    "south_utility_wing": (-14.8, 8.0, -18.0, -4.0, 0.0, 4.2),
    "east_service_loop": (8.0, 23.0, -18.0, 18.0, 0.0, 4.2),
}


def read_ascii_pcd(path: Path) -> List[Tuple[float, float, float]]:
    points: List[Tuple[float, float, float]] = []
    data_seen = False
    with path.open("r", encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            if not data_seen:
                if line.upper().startswith("DATA"):
                    if line.lower() != "data ascii":
                        raise ValueError("only ASCII PCD is supported: {}".format(path))
                    data_seen = True
                continue
            values = line.split()
            if len(values) < 3:
                continue
            points.append((float(values[0]), float(values[1]), float(values[2])))
    if not data_seen:
        raise ValueError("PCD DATA header not found: {}".format(path))
    return points


def in_region(point: Tuple[float, float, float], region: Sequence[float]) -> bool:
    x, y, z = point
    x0, x1, y0, y1, z0, z1 = region
    return x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1


def voxelize(points: Iterable[Tuple[float, float, float]], resolution: float) -> set:
    return {
        (int(math.floor(x / resolution)), int(math.floor(y / resolution)), int(math.floor(z / resolution)))
        for x, y, z in points
    }


def nearby(voxel: Tuple[int, int, int], tolerance: int):
    x, y, z = voxel
    for dx in range(-tolerance, tolerance + 1):
        for dy in range(-tolerance, tolerance + 1):
            for dz in range(-tolerance, tolerance + 1):
                yield x + dx, y + dy, z + dz


def count_matches(reference: set, candidate: set, tolerance: int) -> int:
    return sum(any(neighbor in candidate for neighbor in nearby(voxel, tolerance)) for voxel in reference)


TRAJECTORY_COORDINATE_ALIASES = {
    "x": ("x", "x_m", "position_x", "pose_x", "px"),
    "y": ("y", "y_m", "position_y", "pose_y", "py"),
    "z": ("z", "z_m", "position_z", "pose_z", "pz"),
}


def load_trajectory(path: Path | None) -> Tuple[List[Tuple[float, float, float]], Dict[str, str]]:
    if path is None:
        return [], {}
    with path.open("r", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return [], {}

    headers = {key.strip().lower(): key for key in rows[0] if key}
    fields = {}
    for axis, aliases in TRAJECTORY_COORDINATE_ALIASES.items():
        field = next((headers[alias] for alias in aliases if alias in headers), None)
        if field is None:
            available = ", ".join(sorted(headers.values()))
            raise ValueError(
                "trajectory CSV must provide x/y/z coordinate columns; "
                "accepted aliases include x_m/y_m/z_m. Available columns: {} ({})".format(available, path)
            )
        fields[axis] = field

    positions = []
    for row in rows:
        try:
            positions.append((float(row[fields["x"]]), float(row[fields["y"]]), float(row[fields["z"]])))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid trajectory coordinate row in {}: {}".format(path, error))
    return positions, fields


def metrics(truth: set, observed: set, tolerance: int) -> Dict[str, float | int | None]:
    if not truth:
        return {"truth_voxels": 0, "observed_voxels": len(observed), "precision": None, "recall": None, "f1": None}
    truth_matches = count_matches(truth, observed, tolerance)
    observed_matches = count_matches(observed, truth, tolerance) if observed else 0
    recall = truth_matches / float(len(truth))
    precision = observed_matches / float(len(observed)) if observed else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_truth_voxels": truth_matches,
        "matched_observed_voxels": observed_matches,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--observed-pcd", required=True)
    parser.add_argument("--trajectory-csv")
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.resolution_m <= 0 or args.tolerance_voxels < 0:
        raise SystemExit("resolution must be positive and tolerance must be nonnegative")

    truth_points = read_ascii_pcd(Path(args.truth_pcd))
    observed_points = read_ascii_pcd(Path(args.observed_pcd))
    trajectory, trajectory_fields = load_trajectory(Path(args.trajectory_csv)) if args.trajectory_csv else ([], {})
    report = {
        "schema_version": 1,
        "mode": "offline_post_run_diagnostic_only",
        "runtime_contract": {
            "truth_map_usage": "offline evaluation only",
            "regions_provided_to_runtime": False,
            "route_prior_used": False,
            "goal_prior_used": False,
        },
        "metric": "per_region_voxel_surface_precision_recall_f1",
        "resolution_m": args.resolution_m,
        "tolerance_voxels": args.tolerance_voxels,
        "trajectory": {
            "path": args.trajectory_csv,
            "coordinate_fields": trajectory_fields,
            "samples": len(trajectory),
        },
        "regions": {},
    }
    for name, bounds in REGIONS.items():
        truth = voxelize((point for point in truth_points if in_region(point, bounds)), args.resolution_m)
        observed = voxelize((point for point in observed_points if in_region(point, bounds)), args.resolution_m)
        sampled_positions = sum(in_region(point, bounds) for point in trajectory)
        report["regions"][name] = {
            "bounds_m": {"x": [bounds[0], bounds[1]], "y": [bounds[2], bounds[3]], "z": [bounds[4], bounds[5]]},
            "trajectory_samples_in_region": sampled_positions,
            **metrics(truth, observed, args.tolerance_voxels),
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
