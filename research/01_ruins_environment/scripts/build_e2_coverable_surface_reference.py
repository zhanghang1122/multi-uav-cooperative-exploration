#!/usr/bin/env python3
"""Build a trajectory-independent, visibility-constrained E2 surface reference.

The output is for offline evaluation only.  It is derived from fixed scene
geometry, a collision-clear sensor-pose lattice, the common indoor flight
band, and the FUEL camera range/FOV.  No experiment trajectory, online map,
Frontier state, room label, goal, or route is read or published.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass

import generate_e2_primary_benchmark as e2


@dataclass(frozen=True)
class PreparedBox:
    source: object
    cosine: float
    sine: float
    aabb_min: tuple
    aabb_max: tuple


def prepare_box(box):
    cosine, sine = math.cos(box.yaw), math.sin(box.yaw)
    half_x, half_y, half_z = (value / 2.0 for value in box.size)
    world_half_x = abs(cosine) * half_x + abs(sine) * half_y
    world_half_y = abs(sine) * half_x + abs(cosine) * half_y
    return PreparedBox(
        source=box,
        cosine=cosine,
        sine=sine,
        aabb_min=(box.center[0] - world_half_x, box.center[1] - world_half_y, box.center[2] - half_z),
        aabb_max=(box.center[0] + world_half_x, box.center[1] + world_half_y, box.center[2] + half_z),
    )


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
    indexes = [fields.index(axis) for axis in ("x", "y", "z")]
    points = []
    for line in lines[data_offset:]:
        tokens = line.split()
        if len(tokens) > max(indexes):
            points.append(tuple(float(tokens[index]) for index in indexes))
    return points


def voxel_of(point, resolution):
    return tuple(int(math.floor(value / resolution)) for value in point)


def voxel_center(voxel, resolution):
    return tuple((index + 0.5) * resolution for index in voxel)


def write_pcd(path, voxels, resolution):
    points = [voxel_center(voxel, resolution) for voxel in sorted(voxels)]
    with open(path, "w", encoding="ascii", newline="\n") as stream:
        stream.write(
            "# .PCD v0.7 - Point Cloud Data file format\n"
            "VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n"
        )
        stream.write(
            "WIDTH {0}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
            "POINTS {0}\nDATA ascii\n".format(len(points))
        )
        for point in points:
            stream.write("{:.3f} {:.3f} {:.3f}\n".format(*point))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_xyz(point, prepared):
    box = prepared.source
    dx, dy = point[0] - box.center[0], point[1] - box.center[1]
    local_x = prepared.cosine * dx + prepared.sine * dy
    local_y = -prepared.sine * dx + prepared.cosine * dy
    return local_x, local_y, point[2] - box.center[2]


def sphere_intersects_box(point, radius, prepared):
    if any(
        point[axis] < prepared.aabb_min[axis] - radius
        or point[axis] > prepared.aabb_max[axis] + radius
        for axis in range(3)
    ):
        return False
    box = prepared.source
    local = local_xyz(point, prepared)
    squared_distance = 0.0
    for value, size in zip(local, box.size):
        outside = max(abs(value) - size / 2.0, 0.0)
        squared_distance += outside * outside
    return squared_distance <= radius * radius


def segment_intersects_box(start, end, prepared, endpoint_margin_m):
    """Return True when a segment meets an OBB before its target endpoint."""
    direction = tuple(end[index] - start[index] for index in range(3))
    length = math.sqrt(sum(value * value for value in direction))
    if length <= endpoint_margin_m:
        return False
    fraction = max(0.0, 1.0 - endpoint_margin_m / length)
    shortened_end = tuple(start[index] + fraction * direction[index] for index in range(3))
    for axis in range(3):
        segment_min = min(start[axis], shortened_end[axis])
        segment_max = max(start[axis], shortened_end[axis])
        if segment_max < prepared.aabb_min[axis] or segment_min > prepared.aabb_max[axis]:
            return False
    box = prepared.source
    local_start = local_xyz(start, prepared)
    local_end = local_xyz(shortened_end, prepared)
    t_min, t_max = 0.0, 1.0
    for axis in range(3):
        delta = local_end[axis] - local_start[axis]
        half_size = box.size[axis] / 2.0
        if abs(delta) < 1.0e-12:
            if local_start[axis] < -half_size or local_start[axis] > half_size:
                return False
            continue
        first = (-half_size - local_start[axis]) / delta
        second = (half_size - local_start[axis]) / delta
        if first > second:
            first, second = second, first
        t_min, t_max = max(t_min, first), min(t_max, second)
        if t_min > t_max:
            return False
    return t_max >= 0.0 and t_min <= 1.0


class PoseLattice(object):
    def __init__(self, prepared_boxes, args):
        self.xy = args.pose_xy_resolution_m
        self.z = args.pose_z_resolution_m
        self.min_x = -e2.SIZE[0] / 2.0
        self.min_y = -e2.SIZE[1] / 2.0
        self.min_z = args.candidate_min_z_m
        self.nx = int(math.floor(e2.SIZE[0] / self.xy))
        self.ny = int(math.floor(e2.SIZE[1] / self.xy))
        self.nz = int(math.floor((args.candidate_max_z_m - self.min_z) / self.z)) + 1
        self.free = set()
        for iz in range(self.nz):
            for iy in range(self.ny):
                for ix in range(self.nx):
                    index = (ix, iy, iz)
                    point = self.point(index)
                    if not any(sphere_intersects_box(point, args.clearance_radius_m, box) for box in prepared_boxes):
                        self.free.add(index)
        start = min(self.free, key=lambda index: squared_distance(self.point(index), e2.ENTRY))
        self.start = start
        self.reachable = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for axis in range(3):
                for step in (-1, 1):
                    neighbour = list(current)
                    neighbour[axis] += step
                    neighbour = tuple(neighbour)
                    if neighbour in self.free and neighbour not in self.reachable:
                        self.reachable.add(neighbour)
                        queue.append(neighbour)

    def point(self, index):
        return (
            self.min_x + (index[0] + 0.5) * self.xy,
            self.min_y + (index[1] + 0.5) * self.xy,
            self.min_z + index[2] * self.z,
        )

    def nearest_reachable(self, desired):
        base = (
            int(math.floor((desired[0] - self.min_x) / self.xy)),
            int(math.floor((desired[1] - self.min_y) / self.xy)),
            int(round((desired[2] - self.min_z) / self.z)),
        )
        candidates = []
        for radius in (0, 1, 2):
            for dz in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if max(abs(dx), abs(dy), abs(dz)) != radius:
                            continue
                        index = (base[0] + dx, base[1] + dy, base[2] + dz)
                        if index in self.reachable:
                            candidates.append((squared_distance(self.point(index), desired), index))
            if candidates:
                return self.point(min(candidates)[1])
        return None


def squared_distance(first, second):
    return sum((first[index] - second[index]) ** 2 for index in range(3))


def direction_candidates(normal, vertical_half_fov):
    directions = []
    if abs(normal[2]) < 0.5:
        base_yaw = math.atan2(normal[1], normal[0])
        for yaw_offset_deg, elevation_fraction in (
            (0, 0.0), (-30, 0.0), (30, 0.0), (-60, 0.0), (60, 0.0),
            (0, 0.5), (0, -0.5), (-30, 0.5), (30, 0.5),
            (-30, -0.5), (30, -0.5),
        ):
            yaw = base_yaw + math.radians(yaw_offset_deg)
            elevation = vertical_half_fov * elevation_fraction
            cosine = math.cos(elevation)
            directions.append((cosine * math.cos(yaw), cosine * math.sin(yaw), math.sin(elevation)))
    else:
        sign = 1.0 if normal[2] > 0.0 else -1.0
        for elevation_fraction in (0.92, 0.65, 0.35):
            elevation = sign * vertical_half_fov * elevation_fraction
            cosine = math.cos(elevation)
            for yaw_index in range(8):
                yaw = yaw_index * math.pi / 4.0
                directions.append((cosine * math.cos(yaw), cosine * math.sin(yaw), math.sin(elevation)))
    return directions


def visible_from_pose(target, normal, source_box_index, pose, prepared_boxes, args):
    vector = tuple(pose[index] - target[index] for index in range(3))
    distance = math.sqrt(sum(value * value for value in vector))
    if distance < args.sensor_min_range_m or distance > args.sensor_max_range_m:
        return False
    if sum(vector[index] * normal[index] for index in range(3)) <= 0.0:
        return False
    horizontal = math.hypot(vector[0], vector[1])
    if math.atan2(abs(vector[2]), horizontal) > args.vertical_half_fov_rad:
        return False
    for box_index, box in enumerate(prepared_boxes):
        if box_index == source_box_index:
            continue
        if segment_intersects_box(pose, target, box, args.ray_endpoint_margin_m):
            return False
    return True


def witness_is_coverable(target, normal, source_box_index, lattice, prepared_boxes, args):
    distances = (2.0, 3.0, 4.25, 1.25, 0.75) if abs(normal[2]) >= 0.5 else (1.25, 2.0, 3.0, 4.25, 0.75)
    for direction in direction_candidates(normal, args.vertical_half_fov_rad):
        for distance in distances:
            desired = tuple(target[index] + distance * direction[index] for index in range(3))
            pose = lattice.nearest_reachable(desired)
            if pose is not None and visible_from_pose(target, normal, source_box_index, pose, prepared_boxes, args):
                return True
    return False


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-pcd", required=True)
    parser.add_argument("--output-pcd", required=True)
    parser.add_argument("--noncoverable-pcd")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument(
        "--visibility-sampling-resolution-m",
        type=float,
        default=0.25,
        help="Surface witness lattice used for the visibility audit; output remains at --resolution-m.",
    )
    parser.add_argument("--clearance-radius-m", type=float, default=0.199)
    parser.add_argument("--pose-xy-resolution-m", type=float, default=0.25)
    parser.add_argument("--pose-z-resolution-m", type=float, default=0.25)
    parser.add_argument("--candidate-min-z-m", type=float, default=0.80)
    parser.add_argument("--candidate-max-z-m", type=float, default=1.65)
    parser.add_argument("--sensor-min-range-m", type=float, default=0.5)
    parser.add_argument("--sensor-max-range-m", type=float, default=4.5)
    parser.add_argument("--vertical-half-fov-rad", type=float, default=0.56125)
    parser.add_argument("--virtual-ceiling-z-m", type=float, default=1.85)
    parser.add_argument("--virtual-ceiling-mask-voxels", type=int, default=0)
    parser.add_argument("--ray-endpoint-margin-m", type=float, default=0.08)
    return parser.parse_args()


def main():
    args = parse_args()
    started = time.time()
    numeric_positive = (
        args.resolution_m,
        args.visibility_sampling_resolution_m,
        args.clearance_radius_m,
        args.pose_xy_resolution_m,
        args.pose_z_resolution_m,
        args.sensor_min_range_m,
        args.sensor_max_range_m,
        args.vertical_half_fov_rad,
        args.ray_endpoint_margin_m,
    )
    if any(value <= 0.0 for value in numeric_positive):
        raise SystemExit("resolution, clearance, range, FOV, and endpoint margin must be positive")
    if args.sensor_min_range_m >= args.sensor_max_range_m or args.candidate_min_z_m > args.candidate_max_z_m:
        raise SystemExit("invalid sensor range or candidate height interval")

    boxes = e2.build_e2()
    prepared_boxes = [prepare_box(box) for box in boxes]
    raw_truth = {voxel_of(point, args.resolution_m) for point in read_ascii_pcd(args.truth_pcd)}
    ceiling_index = int(math.floor(args.virtual_ceiling_z_m / args.resolution_m))
    truth = {
        voxel for voxel in raw_truth
        if abs(voxel[2] - ceiling_index) > args.virtual_ceiling_mask_voxels
    }
    lattice = PoseLattice(prepared_boxes, args)
    print(
        "[coverable-reference] pose lattice ready: free={}, reachable={}, elapsed={:.1f}s".format(
            len(lattice.free), len(lattice.reachable), time.time() - started
        ),
        file=sys.stderr,
    )
    coverable = set()
    tested_witnesses = set()
    witness_results = {}
    for box_index, box in enumerate(boxes):
        for point, normal in e2.sample_faces_with_outward_normals(box, e2.PCD_STEP):
            voxel = voxel_of(point, args.resolution_m)
            if voxel not in truth or voxel in coverable:
                continue
            # The supplied interior-reference PCD already performed the exact
            # free-side probe and exterior-face exclusion during generation.
            # Membership in ``truth`` is therefore the authoritative filter;
            # repeating the all-box probe here would be redundant and costly.
            normal_key = tuple(int(round(value)) for value in normal)
            visibility_cell = tuple(
                int(math.floor(value / args.visibility_sampling_resolution_m)) for value in point
            )
            witness_key = (visibility_cell, normal_key, box_index)
            if witness_key not in witness_results:
                tested_witnesses.add(witness_key)
                target = point
                witness_results[witness_key] = witness_is_coverable(
                    target, normal, box_index, lattice, prepared_boxes, args
                )
            if witness_results[witness_key]:
                coverable.add(voxel)
        if box_index % 10 == 0 or box_index + 1 == len(boxes):
            print(
                "[coverable-reference] boxes={}/{}, coverable={}, witnesses={}, elapsed={:.1f}s".format(
                    box_index + 1, len(boxes), len(coverable), len(tested_witnesses), time.time() - started
                ),
                file=sys.stderr,
            )

    noncoverable = truth - coverable
    os.makedirs(os.path.dirname(os.path.abspath(args.output_pcd)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
    write_pcd(args.output_pcd, coverable, args.resolution_m)
    if args.noncoverable_pcd:
        os.makedirs(os.path.dirname(os.path.abspath(args.noncoverable_pcd)), exist_ok=True)
        write_pcd(args.noncoverable_pcd, noncoverable, args.resolution_m)
    checks = {
        "coverable_reference_nonempty": bool(coverable),
        "coverable_is_subset_of_masked_physical_truth": coverable.issubset(truth),
        "entry_sensor_pose_is_reachable": lattice.start in lattice.reachable,
        "entry_reachable_pose_lattice_nonempty": bool(lattice.reachable),
        "coverable_and_noncoverable_partition_truth": coverable.isdisjoint(noncoverable)
        and coverable.union(noncoverable) == truth,
    }
    result = {
        "schema_version": 1,
        "reference": "offline_geometry_visibility_constrained_surface_reference",
        "scene": e2.SCENE_NAME,
        "passed": all(checks.values()),
        "checks": checks,
        "runtime_isolation_contract": {
            "method_independent": True,
            "experiment_trajectory_used": False,
            "online_map_used": False,
            "frontier_state_used": False,
            "room_or_route_prior_used": False,
            "published_to_planner": False,
            "usage": "offline evaluation denominator only",
        },
        "inputs": {
            "truth_pcd": os.path.abspath(args.truth_pcd),
            "truth_pcd_sha256": sha256_file(args.truth_pcd),
            "geometry_source": "generate_e2_primary_benchmark.py fixed build_e2()",
        },
        "parameters": {
            "surface_resolution_m": args.resolution_m,
            "visibility_sampling_resolution_m": args.visibility_sampling_resolution_m,
            "vehicle_clearance_radius_m": args.clearance_radius_m,
            "sensor_pose_lattice_m": [args.pose_xy_resolution_m, args.pose_xy_resolution_m, args.pose_z_resolution_m],
            "candidate_height_m": [args.candidate_min_z_m, args.candidate_max_z_m],
            "sensor_range_m": [args.sensor_min_range_m, args.sensor_max_range_m],
            "vertical_half_fov_rad": args.vertical_half_fov_rad,
            "vertical_half_fov_deg": round(math.degrees(args.vertical_half_fov_rad), 6),
            "horizontal_policy": "existential yaw: a candidate may face an individual surface point",
            "occlusion_test": "exact line segment versus all yaw-only scene boxes",
            "virtual_ceiling_mask": {
                "height_m": args.virtual_ceiling_z_m,
                "voxel_index": ceiling_index,
                "half_width_voxels": args.virtual_ceiling_mask_voxels,
            },
        },
        "counts": {
            "raw_truth_voxels": len(raw_truth),
            "masked_physical_truth_voxels": len(truth),
            "coverable_truth_voxels": len(coverable),
            "noncoverable_truth_voxels": len(noncoverable),
            "coverable_fraction_of_physical_truth": round(len(coverable) / float(max(1, len(truth))), 6),
            "free_sensor_pose_lattice_cells": len(lattice.free),
            "entry_reachable_sensor_pose_lattice_cells": len(lattice.reachable),
            "tested_surface_witnesses": len(tested_witnesses),
        },
        "outputs": {
            "coverable_reference_pcd": os.path.abspath(args.output_pcd),
            "coverable_reference_pcd_sha256": sha256_file(args.output_pcd),
            "noncoverable_reference_pcd": None if not args.noncoverable_pcd else os.path.abspath(args.noncoverable_pcd),
            "noncoverable_reference_pcd_sha256": (
                None if not args.noncoverable_pcd else sha256_file(args.noncoverable_pcd)
            ),
        },
        "limitations": [
            "Coverability is a deterministic discretized approximation, not continuous visibility proof.",
            "All output voxels in one surface witness cell inherit that cell's visibility result.",
            "The camera may choose yaw per tested surface point; no pitch actuation is assumed.",
            "The reference evaluates geometric observability, not localization drift or sensor noise.",
        ],
    }
    with open(args.output_json, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
