#!/usr/bin/env python3
"""Offline voxel-surface Precision, Recall and F1 evaluation for a PCD map."""

from __future__ import print_function

import argparse
import csv
import json
import math
import os


def read_ascii_pcd(path):
    fields = None
    data_offset = None
    with open(path, "r", encoding="utf-8") as stream:
        lines = stream.readlines()
    for index, line in enumerate(lines):
        tokens = line.strip().split()
        if not tokens:
            continue
        key = tokens[0].upper()
        if key == "FIELDS":
            fields = tokens[1:]
        if key == "DATA":
            if len(tokens) != 2 or tokens[1].lower() != "ascii":
                raise RuntimeError("only ASCII PCD is supported: " + path)
            data_offset = index + 1
            break
    if fields is None or data_offset is None:
        raise RuntimeError("invalid PCD header: " + path)
    indexes = {}
    for name in ("x", "y", "z"):
        if name not in fields:
            raise RuntimeError("PCD is missing {} field: {}".format(name, path))
        indexes[name] = fields.index(name)
    points = []
    for line in lines[data_offset:]:
        tokens = line.split()
        if len(tokens) <= max(indexes.values()):
            continue
        points.append((float(tokens[indexes["x"]]), float(tokens[indexes["y"]]), float(tokens[indexes["z"]])))
    return points


def voxelize(points, resolution):
    return set((
        int(math.floor(x / resolution)),
        int(math.floor(y / resolution)),
        int(math.floor(z / resolution)),
    ) for x, y, z in points)


def has_neighbour(voxel, candidates, tolerance):
    x, y, z = voxel
    for dx in range(-tolerance, tolerance + 1):
        for dy in range(-tolerance, tolerance + 1):
            for dz in range(-tolerance, tolerance + 1):
                if (x + dx, y + dy, z + dz) in candidates:
                    return True
    return False


def evaluate_voxels(truth, observed, tolerance):
    if not observed:
        return {
            "observed_voxels": 0,
            "matched_observed_voxels": 0,
            "matched_truth_voxels": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }
    matched_observed = sum(1 for voxel in observed if has_neighbour(voxel, truth, tolerance))
    matched_truth = sum(1 for voxel in truth if has_neighbour(voxel, observed, tolerance))
    precision = float(matched_observed) / len(observed)
    recall = float(matched_truth) / len(truth)
    f1 = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    return {
        "observed_voxels": len(observed),
        "matched_observed_voxels": matched_observed,
        "matched_truth_voxels": matched_truth,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def parse_thresholds(value):
    thresholds = []
    for token in value.split(","):
        threshold = float(token.strip())
        if threshold <= 0.0 or threshold > 1.0:
            raise RuntimeError("coverage thresholds must be in (0, 1]")
        thresholds.append(threshold)
    return sorted(set(thresholds))


def first_crossing_time(rows, threshold):
    previous = None
    for row in rows:
        if row["recall"] >= threshold:
            if previous is None or previous["recall"] >= threshold:
                return row["elapsed_s"]
            delta_recall = row["recall"] - previous["recall"]
            if delta_recall <= 0.0:
                return row["elapsed_s"]
            fraction = (threshold - previous["recall"]) / delta_recall
            return round(previous["elapsed_s"] + fraction * (row["elapsed_s"] - previous["elapsed_s"]), 6)
        previous = row
    return None


def evaluate_snapshots(args, truth):
    if not args.snapshots_csv:
        return None
    rows = []
    base_dir = os.path.dirname(os.path.abspath(args.snapshots_csv))
    with open(args.snapshots_csv, "r", encoding="utf-8") as stream:
        for source_row in csv.DictReader(stream):
            path = source_row["pcd_relative_path"]
            if not os.path.isabs(path):
                path = os.path.join(base_dir, path)
            observed = voxelize(read_ascii_pcd(path), args.resolution_m)
            metric = evaluate_voxels(truth, observed, args.tolerance_voxels)
            rows.append({
                "elapsed_s": float(source_row["elapsed_s"]),
                "occupied_points": int(source_row["occupied_points"]),
                "pcd_path": os.path.abspath(path),
                "precision": round(metric["precision"], 6),
                "recall": round(metric["recall"], 6),
                "f1": round(metric["f1"], 6),
            })
    curve_path = os.path.join(os.path.dirname(os.path.abspath(args.output)), "map_quality_curve.csv")
    with open(curve_path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("elapsed_s", "occupied_points", "precision", "recall", "f1", "pcd_path"))
        writer.writeheader()
        writer.writerows(rows)
    thresholds = parse_thresholds(args.coverage_thresholds)
    return {
        "coverage_definition": "offline interior-reference voxel-surface recall versus elapsed exploration time",
        "coverage_thresholds": thresholds,
        "time_to_surface_recall_s": {
            "T{}".format(int(round(threshold * 100))): first_crossing_time(rows, threshold)
            for threshold in thresholds
        },
        "snapshot_count": len(rows),
        "snapshot_curve_csv": curve_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--observed-pcd", required=True)
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument(
        "--snapshots-csv",
        help="Recorder snapshots.csv. Enables offline surface-recall coverage curves and T80/T90/T95.",
    )
    parser.add_argument("--coverage-thresholds", default="0.80,0.90,0.95")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.resolution_m <= 0.0 or args.tolerance_voxels < 0:
        raise SystemExit("resolution must be positive and tolerance must be non-negative")
    truth = voxelize(read_ascii_pcd(args.truth_pcd), args.resolution_m)
    observed = voxelize(read_ascii_pcd(args.observed_pcd), args.resolution_m)
    if not truth or not observed:
        raise SystemExit("truth and observed maps must both contain points")
    metric = evaluate_voxels(truth, observed, args.tolerance_voxels)
    result = {
        "schema_version": 1,
        "metric": "offline_voxel_surface_precision_recall_f1",
        "truth_map_usage": "offline_evaluation_only",
        "truth_pcd": os.path.abspath(args.truth_pcd),
        "observed_pcd": os.path.abspath(args.observed_pcd),
        "resolution_m": args.resolution_m,
        "tolerance_voxels": args.tolerance_voxels,
        "truth_voxels": len(truth),
        "observed_voxels": metric["observed_voxels"],
        "matched_observed_voxels": metric["matched_observed_voxels"],
        "matched_truth_voxels": metric["matched_truth_voxels"],
        "precision": round(metric["precision"], 6),
        "recall": round(metric["recall"], 6),
        "f1": round(metric["f1"], 6),
    }
    snapshot_metrics = evaluate_snapshots(args, truth)
    if snapshot_metrics is not None:
        result["coverage_time_metrics"] = snapshot_metrics
    with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
