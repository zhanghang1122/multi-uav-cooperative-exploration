#!/usr/bin/env python3
"""Offline voxel-surface Precision, Recall and F1 evaluation for a PCD map."""

from __future__ import print_function

import argparse
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


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--observed-pcd", required=True)
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
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
    matched_observed = sum(1 for voxel in observed if has_neighbour(voxel, truth, args.tolerance_voxels))
    matched_truth = sum(1 for voxel in truth if has_neighbour(voxel, observed, args.tolerance_voxels))
    precision = float(matched_observed) / len(observed)
    recall = float(matched_truth) / len(truth)
    f1 = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    result = {
        "schema_version": 1,
        "metric": "offline_voxel_surface_precision_recall_f1",
        "truth_map_usage": "offline_evaluation_only",
        "truth_pcd": os.path.abspath(args.truth_pcd),
        "observed_pcd": os.path.abspath(args.observed_pcd),
        "resolution_m": args.resolution_m,
        "tolerance_voxels": args.tolerance_voxels,
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_observed_voxels": matched_observed,
        "matched_truth_voxels": matched_truth,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }
    with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
