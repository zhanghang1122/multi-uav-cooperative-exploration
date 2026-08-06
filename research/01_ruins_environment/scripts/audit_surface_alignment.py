#!/usr/bin/env python3
"""Diagnose rigid frame misalignment between an observed map and truth PCD.

This is an offline diagnostic. It never changes the official map score, writes
planner inputs, or supplies a transform to the running system. ICP is initialized
at the identity transform because both inputs are contractually expected to use
the same simulation world coordinates.
"""

from __future__ import print_function

import argparse
import json
import math

import numpy as np


def read_ascii_pcd(path):
    fields = None
    data_offset = None
    with open(path, "r", encoding="utf-8") as stream:
        lines = stream.readlines()
    for index, line in enumerate(lines):
        tokens = line.strip().split()
        if not tokens:
            continue
        if tokens[0].upper() == "FIELDS":
            fields = tokens[1:]
        if tokens[0].upper() == "DATA":
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
        if len(tokens) > max(indexes.values()):
            points.append(tuple(float(tokens[indexes[name]]) for name in ("x", "y", "z")))
    return points


def voxelize(points, resolution):
    return {
        tuple(int(math.floor(value / resolution)) for value in point)
        for point in points
    }


def has_neighbour(voxel, candidates, tolerance):
    x, y, z = voxel
    for dx in range(-tolerance, tolerance + 1):
        for dy in range(-tolerance, tolerance + 1):
            for dz in range(-tolerance, tolerance + 1):
                if (x + dx, y + dy, z + dz) in candidates:
                    return True
    return False


def evaluate_voxels(truth, observed, tolerance):
    matched_observed = sum(has_neighbour(voxel, truth, tolerance) for voxel in observed)
    matched_truth = sum(has_neighbour(voxel, observed, tolerance) for voxel in truth)
    precision = matched_observed / float(len(observed)) if observed else 0.0
    recall = matched_truth / float(len(truth)) if truth else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_truth_voxels": matched_truth,
        "matched_observed_voxels": matched_observed,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def virtual_ceiling_voxel(args):
    if args.virtual_ceiling_z_m is None:
        return None
    return int(math.floor(args.virtual_ceiling_z_m / args.resolution_m))


def mask_virtual_ceiling(voxels, ceiling_voxel, half_width):
    if ceiling_voxel is None:
        return voxels
    return {voxel for voxel in voxels if abs(voxel[2] - ceiling_voxel) > half_width}


def mask_virtual_ceiling_points(points, resolution, ceiling_voxel, half_width_voxels):
    if ceiling_voxel is None:
        return points
    return [
        point
        for point in points
        if abs(int(math.floor(point[2] / resolution)) - ceiling_voxel) > half_width_voxels
    ]


def deterministic_downsample(points, resolution, max_points):
    selected = {}
    for point in points:
        key = tuple(int(math.floor(value / resolution)) for value in point)
        if key not in selected:
            selected[key] = point
    values = [selected[key] for key in sorted(selected)]
    if len(values) > max_points:
        stride = int(math.ceil(len(values) / float(max_points)))
        values = values[::stride]
    return np.asarray(values, dtype=float)


class SpatialHash(object):
    def __init__(self, points, cell_size):
        self.points = points
        self.cell_size = cell_size
        self.cells = {}
        for index, point in enumerate(points):
            key = self.key(point)
            self.cells.setdefault(key, []).append(index)

    def key(self, point):
        return tuple(int(math.floor(value / self.cell_size)) for value in point)

    def nearest(self, point, max_distance):
        origin = self.key(point)
        radius = int(math.ceil(max_distance / self.cell_size))
        best_index = None
        best_squared = max_distance * max_distance
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    for index in self.cells.get((origin[0] + dx, origin[1] + dy, origin[2] + dz), ()):
                        delta = self.points[index] - point
                        squared = float(np.dot(delta, delta))
                        if squared < best_squared:
                            best_squared = squared
                            best_index = index
        return best_index, math.sqrt(best_squared) if best_index is not None else None


def rigid_fit(source, target):
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T.dot(target - target_center)
    u, _singular, vt = np.linalg.svd(covariance)
    rotation = vt.T.dot(u.T)
    if np.linalg.det(rotation) < 0.0:
        vt[-1, :] *= -1.0
        rotation = vt.T.dot(u.T)
    translation = target_center - rotation.dot(source_center)
    return rotation, translation


def rotation_angle_deg(rotation):
    cosine = max(-1.0, min(1.0, (float(np.trace(rotation)) - 1.0) / 2.0))
    return math.degrees(math.acos(cosine))


def run_icp(source, target, max_distance, trim_fraction, iterations):
    index = SpatialHash(target, max_distance)
    rotation = np.eye(3)
    translation = np.zeros(3)
    history = []
    for iteration in range(iterations):
        transformed = source.dot(rotation.T) + translation
        pairs = []
        for point_index, point in enumerate(transformed):
            target_index, distance = index.nearest(point, max_distance)
            if target_index is not None:
                pairs.append((distance, point_index, target_index))
        if len(pairs) < 20:
            raise RuntimeError("ICP found fewer than 20 local correspondences")
        pairs.sort(key=lambda item: item[0])
        keep = max(20, int(len(pairs) * trim_fraction))
        pairs = pairs[:keep]
        current = np.asarray([transformed[item[1]] for item in pairs])
        matched = np.asarray([target[item[2]] for item in pairs])
        delta_rotation, delta_translation = rigid_fit(current, matched)
        rotation = delta_rotation.dot(rotation)
        translation = delta_rotation.dot(translation) + delta_translation
        rmse = math.sqrt(sum(item[0] * item[0] for item in pairs) / len(pairs))
        step_translation = float(np.linalg.norm(delta_translation))
        step_rotation = rotation_angle_deg(delta_rotation)
        history.append({
            "iteration": iteration + 1,
            "correspondences": len(pairs),
            "rmse_m": round(rmse, 6),
            "step_translation_m": round(step_translation, 6),
            "step_rotation_deg": round(step_rotation, 6),
        })
        if step_translation < 1e-5 and step_rotation < 1e-4:
            break
    return rotation, translation, history


def bounds(points):
    array = np.asarray(points, dtype=float)
    return {
        "min": [round(value, 6) for value in array.min(axis=0).tolist()],
        "max": [round(value, 6) for value in array.max(axis=0).tolist()],
        "centroid": [round(value, 6) for value in array.mean(axis=0).tolist()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--observed-pcd", required=True)
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--tolerance-voxels", type=int, default=1)
    parser.add_argument("--virtual-ceiling-z-m", type=float)
    parser.add_argument("--virtual-ceiling-mask-voxels", type=int, default=0)
    parser.add_argument("--icp-downsample-m", type=float, default=0.2)
    parser.add_argument("--max-correspondence-m", type=float, default=0.3)
    parser.add_argument("--trim-fraction", type=float, default=0.8)
    parser.add_argument("--max-points", type=int, default=8000)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.resolution_m <= 0.0 or args.icp_downsample_m <= 0.0 or args.max_correspondence_m <= 0.0:
        raise SystemExit("resolutions and correspondence distance must be positive")
    if not 0.1 <= args.trim_fraction <= 1.0 or args.max_points < 20 or args.iterations < 1:
        raise SystemExit("invalid ICP trim, point-count, or iteration parameter")

    truth_points = read_ascii_pcd(args.truth_pcd)
    observed_points = read_ascii_pcd(args.observed_pcd)
    ceiling = virtual_ceiling_voxel(args)
    truth_points_for_icp = mask_virtual_ceiling_points(
        truth_points, args.resolution_m, ceiling, args.virtual_ceiling_mask_voxels
    )
    observed_points_for_icp = mask_virtual_ceiling_points(
        observed_points, args.resolution_m, ceiling, args.virtual_ceiling_mask_voxels
    )
    truth_voxels = mask_virtual_ceiling(voxelize(truth_points, args.resolution_m), ceiling, args.virtual_ceiling_mask_voxels)
    observed_voxels = mask_virtual_ceiling(voxelize(observed_points, args.resolution_m), ceiling, args.virtual_ceiling_mask_voxels)
    direct = evaluate_voxels(truth_voxels, observed_voxels, args.tolerance_voxels)

    source = deterministic_downsample(observed_points_for_icp, args.icp_downsample_m, args.max_points)
    target = deterministic_downsample(truth_points_for_icp, args.icp_downsample_m, args.max_points * 4)
    rotation, translation, history = run_icp(
        source, target, args.max_correspondence_m, args.trim_fraction, args.iterations
    )
    registered_points = [
        tuple(rotation.dot(np.asarray(point)) + translation)
        for point in observed_points_for_icp
    ]
    registered_voxels = mask_virtual_ceiling(
        voxelize(registered_points, args.resolution_m), ceiling, args.virtual_ceiling_mask_voxels
    )
    registered = evaluate_voxels(truth_voxels, registered_voxels, args.tolerance_voxels)
    translation_norm = float(np.linalg.norm(translation))
    angle = rotation_angle_deg(rotation)
    recall_gain = registered["recall"] - direct["recall"]
    frame_misalignment_supported = (
        direct["precision"] < 0.95
        and recall_gain > 0.02
        and (translation_norm > args.resolution_m or angle > 1.0)
    )
    report = {
        "schema_version": 1,
        "mode": "offline_identity_initialized_icp_diagnostic",
        "official_score_modified": False,
        "inputs": {
            "truth_pcd": args.truth_pcd,
            "observed_pcd": args.observed_pcd,
            "truth_bounds_m": bounds(truth_points),
            "observed_bounds_m": bounds(observed_points),
        },
        "parameters": {
            "resolution_m": args.resolution_m,
            "tolerance_voxels": args.tolerance_voxels,
            "icp_downsample_m": args.icp_downsample_m,
            "max_correspondence_m": args.max_correspondence_m,
            "trim_fraction": args.trim_fraction,
        },
        "direct_score": direct,
        "diagnostic_registered_score": registered,
        "diagnostic_transform_observed_to_truth": {
            "rotation_matrix": [[round(value, 9) for value in row] for row in rotation.tolist()],
            "translation_m": [round(value, 9) for value in translation.tolist()],
            "translation_norm_m": round(translation_norm, 9),
            "rotation_angle_deg": round(angle, 9),
        },
        "recall_gain": round(recall_gain, 6),
        "frame_misalignment_hypothesis_supported": frame_misalignment_supported,
        "icp_history": history,
        "interpretation": (
            "ICP is diagnostic only. A near-identity transform with little recall gain rejects rigid frame mismatch; "
            "it does not prove that the truth denominator is observable or that exploration is complete."
        ),
    }
    with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
