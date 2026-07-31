#!/usr/bin/env python3
"""Generate auditable damaged-building exploration benchmark assets.

This is deliberately a *scene generator*, not an exploration program.  The
generated PCD is an offline truth map for evaluation; the Gazebo scene contains
only collision/visual geometry.  It contains no navigation graph, room id,
frontier, route, task allocation or target location for a runtime UAV.

The layouts use a controlled scene family, as is common in autonomous aerial
exploration studies: a functional structured interior (E1), a damaged building
interior for the main comparison (E2), and a topologically different damaged
industrial wing (E3) for generalization.  Their structural/topological counts
are written to validation reports so that complexity is reproducible rather
than inferred from a screenshot.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import zlib
from collections import Counter, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

# Catkin's devel-space script wrapper executes this source file from another
# directory.  Keep the adjacent exporter import valid for both `rosrun` and a
# direct `python3` invocation without modifying the upstream exporter.
SOURCE_DIR = Path(__file__).resolve().parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from generate_ruins_package import Box, write_dae, write_mtl, write_obj, write_pcd


ROOT = Path(__file__).resolve().parents[1]
WALL_T = 0.28
PCD_STEP_M = 0.12
FLIGHT_SLICE_Z = 1.50


@dataclass(frozen=True)
class Scene:
    key: str
    title: str
    size: tuple[float, float, float]
    entry: tuple[float, float, float]
    purpose: str
    topology: dict


SCENES = (
    Scene(
        "e1_structured_interior",
        "Coop-Building-E1-Structured-Interior",
        (26.0, 22.0, 3.6),
        (-12.1, 0.0, 1.5),
        "Interface check and single-UAV functional baseline; not the primary result scene.",
        {"rooms": 8, "junctions": 4, "loops": 1, "dead_ends": 2, "bottlenecks": 1, "occluding_turns": 6, "damage_clusters": 1},
    ),
    Scene(
        "e2_damaged_building",
        "Coop-Building-E2-Damaged-Building",
        (42.0, 32.0, 4.2),
        (-20.0, 0.0, 1.5),
        "Primary fixed scene for B1/B2/B3/P comparisons: connected damaged building with loops, branches, occlusions and bounded debris.",
        {"rooms": 16, "junctions": 10, "loops": 4, "dead_ends": 6, "bottlenecks": 4, "occluding_turns": 18, "damage_clusters": 6},
    ),
    Scene(
        "e3_industrial_wing",
        "Coop-Building-E3-Industrial-Wing",
        (50.0, 38.0, 4.6),
        (-24.0, 0.0, 1.5),
        "Topology-generalization scene: workshop, service wing and storage cells rather than a scaled copy of E2.",
        {"rooms": 20, "junctions": 14, "loops": 6, "dead_ends": 10, "bottlenecks": 6, "occluding_turns": 26, "damage_clusters": 8},
    ),
)

COLORS = {
    "concrete": "#b6b0a8", "concrete_light": "#d5d0c8", "dark_concrete": "#4c5152",
    "rubble": "#816b57", "brick": "#814d3d", "rebar": "#4b332d",
}


def write_text_lf(path: Path, text: str):
    """Write stable LF text on Ubuntu 20.04 / Python 3.8 and newer."""
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(text)


def add_box(boxes: list[Box], name: str, center, size, material="concrete", role="obstacle", yaw=0.0):
    boxes.append(Box(name, tuple(center), tuple(size), (0.0, 0.0, yaw), material, role))


def add_wall(boxes: list[Box], name: str, a, b, height, material="concrete", role="wall"):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        return
    add_box(boxes, name, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, height / 2), (length, WALL_T, height), material, role, math.atan2(dy, dx))


def add_open_wall(boxes: list[Box], name: str, a, b, openings: Iterable[tuple[float, float]], height, material="concrete"):
    """Create a wall with geometric openings; opening positions are arclengths."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        return
    ux, uy = dx / length, dy / length
    spans = sorted((max(0.0, c - w / 2), min(length, c + w / 2)) for c, w in openings)
    cursor, part = 0.0, 0
    for left, right in spans + [(length, length)]:
        if left - cursor > 0.08:
            p = (a[0] + cursor * ux, a[1] + cursor * uy)
            q = (a[0] + left * ux, a[1] + left * uy)
            add_wall(boxes, f"{name}_{part:02d}", p, q, height, material)
            part += 1
        cursor = max(cursor, right)


def envelope(boxes: list[Box], scene: Scene):
    width, depth, height = scene.size
    hx, hy = width / 2, depth / 2
    add_box(boxes, "floor_slab", (0.0, 0.0, -0.10), (width, depth, 0.20), "dark_concrete", "floor")
    add_wall(boxes, "envelope_north", (-hx, hy), (hx, hy), height)
    add_wall(boxes, "envelope_south", (-hx, -hy), (hx, -hy), height)
    add_wall(boxes, "envelope_east", (hx, -hy), (hx, hy), height)
    # The entry is physical geometry only.  It conveys no task direction or route.
    add_open_wall(boxes, "envelope_west", (-hx, -hy), (-hx, hy), [(hy, 2.8)], height)


def add_columns(boxes: list[Box], prefix: str, coordinates, height):
    for index, (x, y) in enumerate(coordinates):
        add_box(boxes, f"{prefix}_{index:02d}", (x, y, height / 2), (0.56, 0.56, height), "concrete_light", "column")


def add_equipment(boxes: list[Box], prefix: str, items):
    for index, (x, y, sx, sy, sz, yaw) in enumerate(items):
        add_box(boxes, f"{prefix}_{index:02d}", (x, y, sz / 2), (sx, sy, sz), "brick", "equipment", yaw)


def add_damage(boxes: list[Box], prefix: str, items):
    """Damage is constrained to rooms/alcoves, never laid across a declared corridor."""
    for index, (x, y, sx, sy, sz, yaw) in enumerate(items):
        add_box(boxes, f"{prefix}_{index:02d}", (x, y, sz / 2), (sx, sy, sz), "rubble", "damage", yaw)


def add_overhead(boxes: list[Box], prefix: str, items):
    for index, (x, y, sx, sy, z) in enumerate(items):
        add_box(boxes, f"{prefix}_{index:02d}", (x, y, z), (sx, sy, 0.24), "concrete_light", "overhead")


def iter_face_points_with_outward_normal(box: Box, step: float):
    """Uniformly sample box faces and retain the outward normal of each point."""
    sx, sy, sz = box.size
    yaw = box.rpy[2]
    cosine, sine = math.cos(yaw), math.sin(yaw)
    faces = (
        ("x", -sx / 2, sy, sz, (-1.0, 0.0, 0.0)),
        ("x", sx / 2, sy, sz, (1.0, 0.0, 0.0)),
        ("y", -sy / 2, sx, sz, (0.0, -1.0, 0.0)),
        ("y", sy / 2, sx, sz, (0.0, 1.0, 0.0)),
        ("z", -sz / 2, sx, sy, (0.0, 0.0, -1.0)),
        ("z", sz / 2, sx, sy, (0.0, 0.0, 1.0)),
    )
    for axis, constant, length_a, length_b, local_normal in faces:
        count_a = max(1, int(math.ceil(length_a / step)))
        count_b = max(1, int(math.ceil(length_b / step)))
        for index_a in range(count_a + 1):
            value_a = -length_a / 2 + length_a * index_a / count_a
            for index_b in range(count_b + 1):
                value_b = -length_b / 2 + length_b * index_b / count_b
                if axis == "x":
                    local = (constant, value_a, value_b)
                elif axis == "y":
                    local = (value_a, constant, value_b)
                else:
                    local = (value_a, value_b, constant)
                point = (
                    box.center[0] + cosine * local[0] - sine * local[1],
                    box.center[1] + sine * local[0] + cosine * local[1],
                    box.center[2] + local[2],
                )
                normal = (
                    cosine * local_normal[0] - sine * local_normal[1],
                    sine * local_normal[0] + cosine * local_normal[1],
                    local_normal[2],
                )
                yield point, normal


def point_inside_box(point, box: Box):
    """Strict inside test; all benchmark boxes are yaw-only rigid bodies."""
    yaw = box.rpy[2]
    cosine, sine = math.cos(yaw), math.sin(yaw)
    dx, dy, dz = point[0] - box.center[0], point[1] - box.center[1], point[2] - box.center[2]
    local_x = cosine * dx + sine * dy
    local_y = -sine * dx + cosine * dy
    return (
        abs(local_x) < box.size[0] / 2
        and abs(local_y) < box.size[1] / 2
        and abs(dz) < box.size[2] / 2
    )


def write_interior_reference_pcd(path: Path, boxes: list[Box], scene: Scene, step: float):
    """Export only interior-facing, geometrically free surface samples.

    This is an *offline evaluation reference*, not a simulator input.  A point
    is retained only when a small step along its outward face normal lies inside
    the building volume and outside every other collision box.  It removes
    exterior envelope faces and bottom faces that an indoor aerial sensor cannot
    observe from reachable building space.
    """
    half_x, half_y = scene.size[0] / 2, scene.size[1] / 2
    clearance = 0.035
    points, seen = [], set()
    for box_index, box in enumerate(boxes):
        if box.role == "connector_marker":
            continue
        for point, normal in iter_face_points_with_outward_normal(box, step):
            probe = (
                point[0] + clearance * normal[0],
                point[1] + clearance * normal[1],
                point[2] + clearance * normal[2],
            )
            if not (-half_x < probe[0] < half_x and -half_y < probe[1] < half_y and 0.0 < probe[2] < scene.size[2]):
                continue
            if any(point_inside_box(probe, other) for other_index, other in enumerate(boxes) if other_index != box_index):
                continue
            rounded = (round(point[0], 3), round(point[1], 3), round(point[2], 3))
            key = (int(rounded[0] * 1000), int(rounded[1] * 1000), int(rounded[2] * 1000))
            if key not in seen:
                seen.add(key)
                points.append(rounded)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("# .PCD v0.7 - Point Cloud Data file format\n")
        stream.write("VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n")
        stream.write("WIDTH {}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {}\nDATA ascii\n".format(len(points), len(points)))
        for x, y, z in points:
            stream.write("{:.3f} {:.3f} {:.3f}\n".format(x, y, z))
    return len(points)


def build_e1(scene: Scene) -> list[Box]:
    boxes: list[Box] = []
    envelope(boxes, scene)
    h = scene.size[2]
    # A compact building: a central hall with rooms on both sides, not a maze.
    add_open_wall(boxes, "e1_north_room_line", (-13, 4.5), (13, 4.5), [(3.0, 2.0), (9.0, 2.0), (18.0, 2.0), (23.0, 2.0)], h)
    add_open_wall(boxes, "e1_south_room_line", (-13, -4.5), (13, -4.5), [(3.5, 2.0), (10.5, 2.0), (17.5, 2.0), (23.0, 2.0)], h)
    for i, x in enumerate((-6.5, 0.0, 6.5)):
        add_open_wall(boxes, f"e1_north_partition_{i}", (x, 4.5), (x, 11), [(3.4, 1.8)], h)
        add_open_wall(boxes, f"e1_south_partition_{i}", (x, -11), (x, -4.5), [(3.2, 1.8)], h)
    add_wall(boxes, "e1_hall_visibility_break_a", (-2.0, -1.5), (1.5, -1.5), 2.2, "concrete_light")
    add_wall(boxes, "e1_hall_visibility_break_b", (3.0, 1.5), (6.0, 1.5), 2.2, "concrete_light")
    add_columns(boxes, "e1_column", [(-9.5, 0.0), (-3.0, 0.0), (3.0, 0.0), (9.5, 0.0)], h)
    add_equipment(boxes, "e1_equipment", [(-9.3, 7.6, 2.2, 0.7, 1.6, 0.0), (-2.5, -7.3, 2.0, 0.8, 1.4, 0.0), (8.6, 7.4, 2.4, 0.7, 1.6, 0.0)])
    add_damage(boxes, "e1_damage", [(10.0, -8.2, 1.5, 1.0, 1.0, 0.32)])
    add_overhead(boxes, "e1_overhead", [(-8.0, 1.8, 3.0, 0.55, 2.95), (8.0, -1.8, 3.0, 0.55, 2.95)])
    return boxes


def build_e2(scene: Scene) -> list[Box]:
    boxes: list[Box] = []
    envelope(boxes, scene)
    h = scene.size[2]
    # A damaged public/service building: main hall, north offices, south utility
    # rooms and east service wing.  The entries in these walls make the graph
    # connected but do not label or allocate any online exploration region.
    add_open_wall(boxes, "e2_north_hall_boundary", (-21, 5.0), (21, 5.0), [(3.2, 2.0), (10.0, 2.2), (17.0, 2.0), (25.5, 2.2), (34.5, 2.0)], h)
    add_open_wall(boxes, "e2_south_hall_boundary", (-21, -5.0), (21, -5.0), [(4.5, 2.0), (12.5, 2.2), (21.0, 2.0), (30.0, 2.2), (37.5, 2.0)], h)
    # North and south wings are divided into usable rooms with offset doors;
    # their geometry creates loops and line-of-sight breaks rather than a grid.
    for index, x in enumerate((-14.0, -6.0, 3.0, 12.0)):
        add_open_wall(boxes, f"e2_north_partition_{index}", (x, 5.0), (x, 16.0), [(5.0 + (index % 2), 1.9)], h)
    for index, x in enumerate((-15.0, -7.0, 2.0, 11.0)):
        add_open_wall(boxes, f"e2_south_partition_{index}", (x, -16.0), (x, -5.0), [(5.2 - (index % 2), 1.9)], h)
    # East service loop with transverse connections; placement leaves real turn
    # pockets and one 1.15 m bottleneck after the 0.199m FUEL envelope.
    add_open_wall(boxes, "e2_east_service_outer", (14.5, -16.0), (14.5, 16.0), [(4.0, 2.0), (14.5, 2.0), (25.5, 2.0)], h)
    add_open_wall(boxes, "e2_east_service_inner", (8.0, -13.0), (8.0, 13.0), [(4.5, 1.6), (13.0, 1.6), (21.5, 1.6)], h)
    add_open_wall(boxes, "e2_east_service_north", (8.0, 10.0), (20.8, 10.0), [(3.5, 2.0), (9.5, 2.0)], h)
    add_open_wall(boxes, "e2_east_service_south", (8.0, -10.0), (20.8, -10.0), [(3.5, 2.0), (9.5, 2.0)], h)
    # Non-rectangular damaged core: it creates occlusion and decision points in
    # the central hall while leaving 2.0m+ circulation routes around it.
    add_wall(boxes, "e2_core_a", (-3.8, -1.8), (1.5, -1.8), 2.6, "concrete_light")
    add_wall(boxes, "e2_core_b", (1.5, -1.8), (3.7, 1.0), 2.6, "concrete_light")
    add_wall(boxes, "e2_core_c", (3.7, 1.0), (0.0, 2.6), 2.6, "concrete_light")
    add_wall(boxes, "e2_core_d", (0.0, 2.6), (-3.8, 1.0), 2.6, "concrete_light")
    add_columns(boxes, "e2_hall_column", [(-17.5, -1.6), (-11.0, 1.8), (-6.0, -2.4), (6.5, 2.0), (11.5, -2.0), (17.5, 1.6), (18.2, -3.0)], h)
    add_equipment(boxes, "e2_equipment", [
        (-18.0, 9.0, 2.8, 0.75, 1.8, 0.0), (-10.0, 11.0, 3.0, 0.75, 1.8, 0.0), (-2.0, 9.0, 2.5, 0.75, 1.8, 0.0),
        (-17.0, -11.0, 2.7, 0.8, 1.8, 0.0), (-9.5, -8.8, 2.6, 0.8, 1.8, 0.0), (0.0, -11.5, 2.5, 0.8, 1.8, 0.0),
        (10.5, 13.0, 2.8, 0.8, 1.9, math.pi / 2), (17.5, 6.8, 2.5, 0.8, 1.9, math.pi / 2), (17.5, -6.8, 2.5, 0.8, 1.9, math.pi / 2),
    ])
    add_damage(boxes, "e2_damage", [
        (-16.5, 13.2, 2.6, 0.8, 1.4, 0.20), (-5.0, 13.0, 2.2, 1.0, 1.2, -0.34), (4.8, -13.0, 2.5, 0.9, 1.3, 0.25),
        (19.0, 12.8, 1.8, 1.2, 1.1, -0.30), (19.0, -12.5, 1.8, 1.2, 1.1, 0.30), (-19.0, -13.0, 1.4, 1.1, 1.0, 0.0),
    ])
    # Partial overhead remains at the ceiling zone, forming 3-D observation
    # occlusion but not inventing a hidden second floor.
    add_overhead(boxes, "e2_overhead", [(-15.0, 2.8, 4.2, 0.60, 3.45), (-8.0, -2.8, 4.0, 0.60, 3.45), (8.5, 3.0, 4.0, 0.60, 3.45), (15.0, -2.8, 4.2, 0.60, 3.45)])
    return boxes


def build_e3(scene: Scene) -> list[Box]:
    boxes: list[Box] = []
    envelope(boxes, scene)
    h = scene.size[2]
    # Deliberately different from E2: a north workshop, south storage rooms,
    # and an east service spine connected by offset cross-corridors.
    add_open_wall(boxes, "e3_workshop_boundary", (-25, 7.0), (25, 7.0), [(4.0, 2.2), (12.0, 2.0), (21.0, 2.2), (31.0, 2.0), (42.0, 2.2)], h)
    add_open_wall(boxes, "e3_storage_boundary", (-25, -7.0), (25, -7.0), [(5.0, 2.0), (15.0, 2.2), (25.0, 2.0), (36.0, 2.2), (45.0, 2.0)], h)
    # Workshop racks create dense, structured occlusion while the aisles are
    # dimensioned to remain wider than the derived normal-clearance bound.
    for i, x in enumerate((-19.0, -12.5, -6.0, 0.5, 7.0, 13.5, 20.0)):
        add_box(boxes, f"e3_workshop_rack_{i:02d}", (x, 12.3, 1.35), (3.8, 1.0, 2.7), "brick", "equipment")
        add_box(boxes, f"e3_workshop_rack_{i:02d}_b", (x, 16.2, 1.35), (3.8, 1.0, 2.7), "brick", "equipment")
    # Southern storage: room walls have alternate door locations so the scene
    # has branch decisions, loops and genuine dead ends, not parallel stripes.
    for i, x in enumerate((-18.0, -10.0, -2.0, 7.0, 16.0)):
        add_open_wall(boxes, f"e3_storage_partition_{i}", (x, -19.0), (x, -7.0), [(4.0 + (i % 2), 1.85)], h)
    add_open_wall(boxes, "e3_service_spine_outer", (17.0, -19.0), (17.0, 7.0), [(4.0, 2.0), (13.0, 1.8), (21.5, 2.0)], h)
    add_open_wall(boxes, "e3_service_spine_inner", (10.5, -16.5), (10.5, 4.5), [(3.5, 1.65), (10.5, 1.65), (17.0, 1.65)], h)
    add_open_wall(boxes, "e3_service_link_n", (10.5, 3.5), (24.8, 3.5), [(4.0, 1.9), (11.0, 1.9)], h)
    add_open_wall(boxes, "e3_service_link_s", (10.5, -12.5), (24.8, -12.5), [(4.0, 1.9), (11.0, 1.9)], h)
    # Central irregular inspection spine blocks direct lines of sight.
    for i, (a, b) in enumerate((((-7.0, -2.2), (-2.0, -2.2)), ((-2.0, -2.2), (-0.5, 1.0)), ((-0.5, 1.0), (4.0, 1.0)), ((4.0, 1.0), (5.5, -1.5)))):
        add_wall(boxes, f"e3_core_{i:02d}", a, b, 2.8, "concrete_light")
    add_columns(boxes, "e3_column", [(-21.0, -2.2), (-15.0, 2.0), (-9.0, -2.5), (-3.0, 2.4), (5.0, -2.3), (12.0, 2.0), (20.0, -2.0), (21.0, 10.0), (21.0, 15.0)], h)
    add_equipment(boxes, "e3_storage_equipment", [(-21.0, -11.0, 2.6, 0.9, 1.8, 0.0), (-14.0, -15.0, 2.6, 0.9, 1.8, 0.0), (-6.0, -11.5, 2.8, 0.9, 1.8, 0.0), (3.0, -15.0, 2.6, 0.9, 1.8, 0.0), (12.0, -15.0, 2.7, 0.9, 1.8, 0.0), (21.0, -16.0, 2.4, 0.9, 1.8, 0.0)])
    add_damage(boxes, "e3_damage", [(-22.0, 4.5, 2.8, 1.2, 1.3, 0.28), (-14.0, -17.0, 2.0, 1.0, 1.2, -0.28), (-4.0, -17.0, 2.2, 1.0, 1.2, 0.20), (6.0, -17.0, 2.2, 1.0, 1.2, -0.18), (19.5, -8.0, 2.5, 1.0, 1.2, 0.35), (22.0, 5.5, 2.4, 1.1, 1.2, -0.25), (1.0, 5.5, 2.0, 0.9, 1.2, 0.20), (-9.0, 5.5, 2.0, 0.9, 1.2, -0.20)])
    add_overhead(boxes, "e3_overhead", [(-17.0, 3.2, 4.5, 0.60, 3.75), (-9.0, -3.2, 4.2, 0.60, 3.75), (1.0, 3.2, 4.2, 0.60, 3.75), (9.0, -3.2, 4.2, 0.60, 3.75), (18.0, 1.8, 4.0, 0.60, 3.75), (20.0, 10.0, 3.5, 0.60, 3.75)])
    return boxes


BUILDERS = {"e1_structured_interior": build_e1, "e2_damaged_building": build_e2, "e3_industrial_wing": build_e3}


def footprint_contains(x: float, y: float, box: Box, inflation: float) -> bool:
    z0, z1 = box.center[2] - box.size[2] / 2, box.center[2] + box.size[2] / 2
    if not (z0 <= FLIGHT_SLICE_Z <= z1):
        return False
    yaw = box.rpy[2]
    dx, dy = x - box.center[0], y - box.center[1]
    c, s = math.cos(yaw), math.sin(yaw)
    lx, ly = c * dx + s * dy, -s * dx + c * dy
    return abs(lx) <= box.size[0] / 2 + inflation and abs(ly) <= box.size[1] / 2 + inflation


def validate_connectivity(boxes: list[Box], scene: Scene, radius: float, cell=0.20) -> dict:
    """Offline QA: all free cells must be reachable after FUEL-envelope inflation."""
    width, depth, _ = scene.size
    nx, ny = int(width / cell), int(depth / cell)
    blocked = set()
    for iy in range(ny):
        y = -depth / 2 + (iy + 0.5) * cell
        for ix in range(nx):
            x = -width / 2 + (ix + 0.5) * cell
            if any(footprint_contains(x, y, box, radius) for box in boxes):
                blocked.add((ix, iy))
    sx, sy = int((scene.entry[0] + width / 2) / cell), int((scene.entry[1] + depth / 2) / cell)
    if (sx, sy) in blocked:
        raise RuntimeError(f"{scene.key}: entry is blocked after planning-envelope inflation")
    seen, queue = {(sx, sy)}, deque([(sx, sy)])
    while queue:
        ix, iy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = ix + dx, iy + dy
            if 0 <= nxt[0] < nx and 0 <= nxt[1] < ny and nxt not in blocked and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    free = nx * ny - len(blocked)
    ratio = len(seen) / max(1, free)
    return {"passed": ratio >= 0.985, "flight_slice_z_m": FLIGHT_SLICE_Z, "grid_resolution_m": cell, "planning_envelope_radius_m": radius, "free_cells": free, "reachable_cells": len(seen), "reachable_fraction": round(ratio, 6)}


def write_world(path: Path, scene: Scene, boxes: list[Box]):
    parts = []
    for box in boxes:
        r, g, b = (0.65, 0.63, 0.59)
        if box.material == "dark_concrete": r, g, b = (0.20, 0.22, 0.23)
        elif box.material == "brick": r, g, b = (0.42, 0.26, 0.20)
        elif box.material == "rubble": r, g, b = (0.46, 0.40, 0.34)
        elif box.material == "concrete_light": r, g, b = (0.72, 0.72, 0.69)
        x, y, z = box.center
        sx, sy, sz = box.size
        rr, pp, yy = box.rpy
        parts.append(f"""  <model name='{box.name}'><static>true</static><pose>{x:.4f} {y:.4f} {z:.4f} {rr:.6f} {pp:.6f} {yy:.6f}</pose><link name='link'><collision name='collision'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry></collision><visual name='visual'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry><material><ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient><diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse></material></visual></link></model>""")
    world = "\n".join(parts)
    write_text_lf(path, f"""<?xml version='1.0'?>
<sdf version='1.6'><world name='{scene.key}'><gravity>0 0 -9.81</gravity><scene><ambient>0.55 0.57 0.59 1</ambient><background>0.69 0.72 0.75 1</background><shadows>true</shadows></scene><include><uri>model://sun</uri></include>
{world}
</world></sdf>
""")


def write_svg(path: Path, scene: Scene, boxes: list[Box]):
    width, depth, _ = scene.size
    scale, pad = 18.0, 30
    canvas_w, canvas_h = width * scale + 2 * pad, depth * scale + 2 * pad
    items = [f"<rect width='{canvas_w:.0f}' height='{canvas_h:.0f}' fill='#f4f6f7'/>"]
    for box in boxes:
        if box.role == "floor":
            continue
        x = pad + (box.center[0] - box.size[0] / 2 + width / 2) * scale
        y = pad + (depth / 2 - box.center[1] - box.size[1] / 2) * scale
        color = COLORS.get(box.material, "#999999")
        angle = -math.degrees(box.rpy[2])
        cx, cy = pad + (box.center[0] + width / 2) * scale, pad + (depth / 2 - box.center[1]) * scale
        items.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{box.size[0] * scale:.2f}' height='{box.size[1] * scale:.2f}' fill='{color}' stroke='#343a40' stroke-width='0.6' transform='rotate({angle:.2f} {cx:.2f} {cy:.2f})'/>")
    ex, ey = pad + (scene.entry[0] + width / 2) * scale, pad + (depth / 2 - scene.entry[1]) * scale
    items.append(f"<circle cx='{ex:.2f}' cy='{ey:.2f}' r='7' fill='#1a9b5a'/><text x='{pad}' y='{canvas_h - 8:.0f}' font-family='sans-serif' font-size='14' fill='#20252a'>{scene.title}: offline design preview only</text>")
    write_text_lf(path, "<svg xmlns='http://www.w3.org/2000/svg' width='%.0f' height='%.0f'>%s</svg>\n" % (canvas_w, canvas_h, "".join(items)))


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def write_preview_png(path: Path, scene: Scene, boxes: list[Box], pixels=1000):
    """Dependency-free raster preview used for human visual review before Gazebo."""
    width = pixels
    height = max(500, round(pixels * scene.size[1] / scene.size[0]))
    image = bytearray([244, 246, 247] * width * height)
    sx, sy = width / scene.size[0], height / scene.size[1]

    def set_pixel(px, py, rgb):
        if 0 <= px < width and 0 <= py < height:
            offset = (py * width + px) * 3
            image[offset:offset + 3] = bytes(rgb)

    palette = {
        "concrete": (182, 176, 168), "concrete_light": (213, 208, 200), "dark_concrete": (60, 66, 69),
        "rubble": (129, 107, 87), "brick": (129, 77, 61), "rebar": (75, 51, 45),
    }
    for box in boxes:
        if box.role == "floor":
            continue
        radius = math.hypot(box.size[0] / 2, box.size[1] / 2)
        x0 = max(0, int((box.center[0] - radius + scene.size[0] / 2) * sx))
        x1 = min(width - 1, int((box.center[0] + radius + scene.size[0] / 2) * sx))
        y0 = max(0, int((scene.size[1] / 2 - box.center[1] - radius) * sy))
        y1 = min(height - 1, int((scene.size[1] / 2 - box.center[1] + radius) * sy))
        c, s = math.cos(box.rpy[2]), math.sin(box.rpy[2])
        hx, hy = box.size[0] / 2, box.size[1] / 2
        color = palette.get(box.material, (150, 150, 150))
        for py in range(y0, y1 + 1):
            y = scene.size[1] / 2 - (py + 0.5) / sy
            for px in range(x0, x1 + 1):
                x = (px + 0.5) / sx - scene.size[0] / 2
                dx, dy = x - box.center[0], y - box.center[1]
                lx, ly = c * dx + s * dy, -s * dx + c * dy
                if abs(lx) <= hx and abs(ly) <= hy:
                    set_pixel(px, py, color)
    ex = int((scene.entry[0] + scene.size[0] / 2) * sx)
    ey = int((scene.size[1] / 2 - scene.entry[1]) * sy)
    for dx in range(-7, 8):
        for dy in range(-7, 8):
            if dx * dx + dy * dy <= 49:
                set_pixel(ex + dx, ey + dy, (26, 155, 90))
    raw = b"".join(b"\x00" + bytes(image[row * width * 3:(row + 1) * width * 3]) for row in range(height))
    payload = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def classify(boxes: list[Box]) -> dict:
    return dict(sorted(Counter(box.role for box in boxes).items()))


def generate(scene: Scene, output: Path, radius: float):
    boxes = BUILDERS[scene.key](scene)
    reachability = validate_connectivity(boxes, scene, radius)
    if not reachability["passed"]:
        raise RuntimeError(f"{scene.key} rejected by connectivity QA: {reachability}")
    for folder in ("worlds", "pcd", "obj", "dae", "previews", "validation"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    stem = scene.title
    write_world(output / "worlds" / f"{stem}.world", scene, boxes)
    write_mtl(output / "obj" / "damage_building_suite.mtl")
    pcd_path = output / "pcd" / f"{stem}.pcd"
    reference_path = output / "pcd" / f"{stem}_interior_reference.pcd"
    points = write_pcd(pcd_path, boxes, PCD_STEP_M)
    reference_points = write_interior_reference_pcd(reference_path, boxes, scene, PCD_STEP_M)
    write_obj(output / "obj" / f"{stem}.obj", boxes, "damage_building_suite.mtl")
    write_dae(output / "dae" / f"{stem}.dae", boxes)
    write_svg(output / "previews" / f"{stem}.svg", scene, boxes)
    write_preview_png(output / "previews" / f"{stem}.png", scene, boxes)
    report = {
        "schema_version": 1,
        "scene": asdict(scene),
        "geometry": {
            "box_count": len(boxes),
            "role_counts": classify(boxes),
            "pcd_step_m": PCD_STEP_M,
            "pcd_points": points,
            "interior_reference_points": reference_points,
        },
        "reachability": reachability,
        "runtime_contract": {
            "runtime_input": "bounded workspace and live onboard sensing only",
            "truth_pcd_usage": "offline evaluation only",
            "primary_evaluation_reference": str(reference_path),
            "reference_definition": "interior-facing geometric surfaces with a free outward probe inside the building volume",
            "route_prior_used": False,
            "goal_prior_used": False,
            "topology_or_room_labels_available_to_runtime": False,
        },
    }
    write_text_lf(output / "validation" / f"{stem}.json", json.dumps(report, indent=2) + "\n")
    return report


def load_radius(profile: Path) -> float:
    data = json.loads(profile.read_text(encoding="ascii"))
    diameter = data.get("vehicle", {}).get("effective_planning_diameter_m")
    if not isinstance(diameter, (int, float)) or diameter <= 0:
        raise ValueError("platform profile has no positive vehicle.effective_planning_diameter_m")
    return diameter / 2.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-profile", default=str(ROOT / "config" / "platform_profiles" / "fuel_marsim_os128_v1.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "generated" / "damage_building_suite_v1"))
    parser.add_argument("--scene", choices=[s.key for s in SCENES] + ["all"], default="all")
    args = parser.parse_args()
    radius = load_radius(Path(args.platform_profile))
    wanted = SCENES if args.scene == "all" else tuple(s for s in SCENES if s.key == args.scene)
    reports = [generate(scene, Path(args.output_dir), radius) for scene in wanted]
    write_text_lf(Path(args.output_dir) / "suite_summary.json", json.dumps({"planning_envelope_radius_m": radius, "reports": reports}, indent=2) + "\n")
    print(json.dumps({"output_dir": args.output_dir, "planning_envelope_radius_m": radius, "scenes": [r["scene"]["key"] for r in reports]}, indent=2))


if __name__ == "__main__":
    main()
