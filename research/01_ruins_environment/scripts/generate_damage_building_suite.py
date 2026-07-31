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
    offline_audit: dict


SCENES = (
    Scene(
        "e1_structured_interior",
        "Coop-Building-E1-Structured-Interior",
        (26.0, 22.0, 3.6),
        (-12.1, 0.0, 1.5),
        "Interface check and single-UAV functional baseline; not the primary result scene.",
        {"rooms": 8, "junctions": 4, "loops": 1, "dead_ends": 2, "bottlenecks": 1, "occluding_turns": 6, "damage_clusters": 1},
        {},
    ),
    Scene(
        "e2_damaged_building",
        "Coop-Building-E2V2-Damaged-Branch-Loop",
        (46.0, 36.0, 4.2),
        (-21.4, 0.0, 1.5),
        "Primary fixed scene for B1/B2/B3/P comparisons: a partially damaged single-storey building with a screened entry, three comparable unknown wings, loops and terminal pockets.",
        {"design_role": "primary_fixed_comparison", "major_wings": 3, "cycle_rank": 1, "terminal_pockets": 5, "scene_revision": "v2"},
        {
            "major_branch_anchors": {
                "north_damaged_wing": (7.0, 14.5),
                "south_damaged_wing": (7.0, -14.5),
                "east_service_loop": (18.0, 0.0),
            },
            "passage_probes": (
                ("north_access", (-10.0, 3.6), "y"),
                ("south_access", (-10.0, -3.6), "y"),
                ("north_east_gate", (8.0, 8.0), "x"),
                ("south_east_gate", (8.0, -8.0), "x"),
                ("east_north_crosslink_inner", (11.0, 10.0), "y"),
                ("east_north_crosslink_outer", (18.6, 10.0), "y"),
                ("east_south_crosslink_inner", (11.0, -10.0), "y"),
                ("east_south_crosslink_outer", (18.6, -10.0), "y"),
            ),
            "branch_distance_max_spread_ratio": 0.25,
            "topology_graph": {
                "nodes": {
                    "entry": (-21.4, 0.0), "foyer": (-16.0, 0.0), "hub": (-10.0, 0.0),
                    "north_gate": (-10.0, 5.5), "north_inner": (-1.5, 8.7),
                    "north_anchor": (7.0, 14.5), "north_terminal": (13.0, 15.2),
                    "south_gate": (-10.0, -5.5), "south_inner": (-1.5, -9.3),
                    "south_anchor": (7.0, -14.5), "south_terminal": (13.0, -15.2),
                    "east_north": (12.0, 8.0), "east_south": (12.0, -8.0),
                    "east_anchor": (18.0, 0.0), "east_north_terminal": (20.7, 12.9),
                    "east_south_terminal": (20.7, -14.1),
                },
                "edges": (
                    ("entry", "foyer"), ("foyer", "hub"),
                    ("hub", "north_gate"), ("north_gate", "north_inner"),
                    ("north_inner", "north_anchor"), ("north_anchor", "north_terminal"),
                    ("hub", "south_gate"), ("south_gate", "south_inner"),
                    ("south_inner", "south_anchor"), ("south_anchor", "south_terminal"),
                    ("north_inner", "east_north"), ("south_inner", "east_south"),
                    ("east_north", "east_anchor"), ("east_south", "east_anchor"),
                    ("east_anchor", "east_north_terminal"), ("east_anchor", "east_south_terminal"),
                ),
            },
        },
    ),
    Scene(
        "e3_industrial_wing",
        "Coop-Building-E3V2-Industrial-Spine",
        (48.0, 38.0, 4.2),
        (-22.4, 0.0, 1.5),
        "Topology-generalization scene: asymmetric workshop, damaged storage cells and an S-shaped service spine rather than a scaled E2 copy.",
        {"design_role": "topology_generalization", "major_wings": 3, "cycle_rank": 2, "terminal_pockets": 5, "scene_revision": "v2"},
        {
            "major_branch_anchors": {
                "north_rack_workshop": (5.0, 15.0),
                "south_storage_cells": (3.0, -15.0),
                "east_service_spine": (19.0, 0.0),
            },
            "passage_probes": (
                ("workshop_access", (-11.0, 4.0), "y"),
                ("storage_access", (-11.0, -4.0), "y"),
                ("service_north_gate", (9.0, 8.5), "x"),
                ("service_south_gate", (9.0, -8.5), "x"),
                ("service_north_crosslink_inner", (12.0, 11.0), "y"),
                ("service_north_crosslink_outer", (19.5, 11.0), "y"),
                ("service_south_crosslink_inner", (12.0, -11.0), "y"),
                ("service_south_crosslink_outer", (19.5, -11.0), "y"),
            ),
            "topology_graph": {
                "nodes": {
                    "entry": (-22.4, 0.0), "foyer": (-16.0, 0.0), "spine_west": (-10.0, 0.0),
                    "workshop": (5.0, 15.0), "storage": (3.0, -15.0), "core": (1.5, 0.0),
                    "service": (19.0, 0.0), "service_north": (13.0, 8.5), "service_south": (13.0, -8.5),
                    "workshop_terminal": (11.0, 17.0), "storage_terminal": (10.0, -17.0),
                    "northwest_terminal": (-18.0, 16.0), "southwest_terminal": (-18.0, -16.0),
                },
                "edges": (
                    ("entry", "foyer"), ("foyer", "spine_west"), ("spine_west", "workshop"),
                    ("spine_west", "storage"), ("spine_west", "core"), ("core", "service"),
                    ("service", "service_north"), ("service", "service_south"),
                    ("service_north", "workshop"), ("service_south", "storage"),
                    ("workshop", "workshop_terminal"), ("storage", "storage_terminal"),
                    ("workshop", "northwest_terminal"), ("storage", "southwest_terminal"),
                ),
            },
        },
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
    # E2-V2 is a damaged building, not a random obstacle field. The common
    # entry has a staggered foyer so that the three wings cannot all be observed
    # from the launch pose. The walls below define physical structure only.
    add_wall(boxes, "e2_foyer_north", (-22.8, 3.6), (-13.0, 3.6), h)
    add_wall(boxes, "e2_foyer_south", (-22.8, -3.6), (-13.0, -3.6), h)
    add_wall(boxes, "e2_foyer_baffle_a", (-18.2, -3.6), (-18.2, 0.9), 2.65, "concrete_light")
    add_wall(boxes, "e2_foyer_baffle_b", (-15.0, 3.6), (-15.0, -0.9), 2.65, "concrete_light")
    # A hub separates the three exploration directions. The north and south
    # boundaries have several different doorway scales; the east wing is only
    # reachable through the north/south gates, creating a real loop decision.
    add_open_wall(boxes, "e2_north_boundary", (-13.0, 3.6), (8.0, 3.6), [(3.0, 2.0), (11.0, 1.45), (18.0, 1.15)], h)
    add_open_wall(boxes, "e2_south_boundary", (-13.0, -3.6), (8.0, -3.6), [(3.0, 2.0), (11.0, 1.45), (18.0, 1.15)], h)
    # North wing: an outer gallery, offset rooms and a rear return link. Every
    # structural component either blocks sight or creates a feasible route choice.
    for index, x in enumerate((-9.5, -2.0, 5.5)):
        add_open_wall(boxes, f"e2_north_partition_{index}", (x, 3.6), (x, 17.8), [(4.2 + (index % 2) * 2.4, 1.35 + (index % 2) * 0.25)], h)
    add_open_wall(boxes, "e2_north_rear_gallery", (-13.0, 13.2), (8.0, 13.2), [(4.2, 1.3), (11.8, 1.55), (18.2, 1.3)], 2.55, "concrete_light")
    add_wall(boxes, "e2_north_occluder_a", (-12.0, 7.4), (-8.1, 7.4), 2.45, "concrete_light")
    add_wall(boxes, "e2_north_occluder_b", (-4.2, 10.1), (-0.8, 10.1), 2.45, "concrete_light")
    add_wall(boxes, "e2_north_occluder_c", (2.0, 15.5), (5.0, 15.5), 2.35, "concrete_light")
    # South wing is a different but workload-comparable damaged utility layout.
    for index, x in enumerate((-9.5, -2.0, 5.5)):
        add_open_wall(boxes, f"e2_south_partition_{index}", (x, -17.8), (x, -3.6), [(4.0 + ((index + 1) % 2) * 2.5, 1.35 + ((index + 1) % 2) * 0.25)], h)
    add_open_wall(boxes, "e2_south_rear_gallery", (-13.0, -13.2), (8.0, -13.2), [(4.0, 1.3), (11.5, 1.55), (18.1, 1.3)], 2.55, "concrete_light")
    add_wall(boxes, "e2_south_occluder_a", (-12.0, -7.4), (-8.1, -7.4), 2.45, "concrete_light")
    add_wall(boxes, "e2_south_occluder_b", (-4.2, -10.1), (-0.8, -10.1), 2.45, "concrete_light")
    add_wall(boxes, "e2_south_occluder_c", (2.0, -15.5), (5.0, -15.5), 2.35, "concrete_light")
    # East service loop: two gateway doors from the north/south wings and two
    # cross-links around a damaged core. It gives a coordination policy the
    # option to avoid redundant return travel without exposing a static graph.
    add_open_wall(boxes, "e2_east_gate", (8.0, -14.8), (8.0, 14.8), [(6.8, 1.25), (22.8, 1.25)], h)
    add_open_wall(boxes, "e2_east_outer", (17.0, -17.8), (17.0, 17.8), [(7.8, 1.45), (17.9, 1.35), (28.0, 1.45)], h)
    add_open_wall(boxes, "e2_east_north_crosslink", (8.0, 10.0), (22.8, 10.0), [(3.0, 1.45), (10.6, 1.15)], h)
    add_open_wall(boxes, "e2_east_south_crosslink", (8.0, -10.0), (22.8, -10.0), [(3.0, 1.45), (10.6, 1.15)], h)
    add_wall(boxes, "e2_east_core_a", (11.0, -4.2), (15.0, -4.2), 2.65, "concrete_light")
    add_wall(boxes, "e2_east_core_b", (15.0, -4.2), (16.0, 0.0), 2.65, "concrete_light")
    add_wall(boxes, "e2_east_core_c", (16.0, 0.0), (13.0, 4.0), 2.65, "concrete_light")
    add_wall(boxes, "e2_east_core_d", (13.0, 4.0), (10.5, 1.5), 2.65, "concrete_light")
    add_columns(boxes, "e2_column", [(-12.0, 1.5), (-7.0, -1.8), (-1.0, 1.8), (4.5, -1.8), (-10.0, 10.0), (-2.0, 15.0), (-10.0, -10.0), (-2.0, -15.0), (19.5, 5.5), (19.5, -5.5)], h)
    add_equipment(boxes, "e2_equipment", [
        (-11.0, 15.5, 2.4, 0.75, 1.8, 0.0), (-6.2, 5.8, 2.6, 0.80, 1.7, 0.0), (1.5, 6.4, 2.4, 0.8, 1.7, 0.0), (6.4, 15.7, 2.1, 0.8, 1.6, 0.0),
        (-11.0, -15.5, 2.4, 0.75, 1.8, 0.0), (-6.2, -5.8, 2.6, 0.80, 1.7, 0.0), (1.5, -6.4, 2.4, 0.8, 1.7, 0.0), (6.4, -15.7, 2.1, 0.8, 1.6, 0.0),
        (20.0, 14.0, 2.3, 0.9, 1.8, math.pi / 2), (20.0, -14.0, 2.3, 0.9, 1.8, math.pi / 2), (20.5, 0.0, 2.2, 0.9, 1.7, math.pi / 2),
    ])
    add_damage(boxes, "e2_damage", [
        (-9.8, 16.3, 2.4, 1.0, 1.2, 0.25), (-2.5, 14.8, 2.1, 1.1, 1.25, -0.30), (6.8, 6.0, 1.8, 1.0, 1.1, 0.20),
        (-9.8, -16.3, 2.4, 1.0, 1.2, -0.25), (-2.5, -14.8, 2.1, 1.1, 1.25, 0.30), (6.8, -6.0, 1.8, 1.0, 1.1, -0.20),
        (20.5, 8.0, 1.8, 1.2, 1.15, 0.15), (20.5, -8.0, 1.8, 1.2, 1.15, -0.15),
    ])
    # Ceiling-zone fragments make only local 3-D perception occlusion. There
    # is no hidden upper storey or inaccessible exploration objective.
    add_overhead(boxes, "e2_overhead", [(-10.5, 2.4, 3.6, 0.55, 3.45), (-3.0, -2.4, 3.8, 0.55, 3.45), (-1.5, 11.2, 3.8, 0.55, 3.45), (-1.5, -11.2, 3.8, 0.55, 3.45), (13.5, 6.3, 3.6, 0.55, 3.45), (13.5, -6.3, 3.6, 0.55, 3.45)])
    return boxes


def build_e3(scene: Scene) -> list[Box]:
    boxes: list[Box] = []
    envelope(boxes, scene)
    h = scene.size[2]
    # E3-V2 changes topology, not merely obstacle count. A rack workshop,
    # serial damaged storage cells and an S-shaped service spine create an
    # asymmetric generalization problem after P is frozen on E2-V2.
    add_wall(boxes, "e3_foyer_north", (-23.8, 4.0), (-13.0, 4.0), h)
    add_wall(boxes, "e3_foyer_south", (-23.8, -4.0), (-13.0, -4.0), h)
    add_wall(boxes, "e3_foyer_baffle_a", (-19.0, -4.0), (-19.0, 1.0), 2.65, "concrete_light")
    add_wall(boxes, "e3_foyer_baffle_b", (-15.4, 4.0), (-15.4, -1.0), 2.65, "concrete_light")
    add_open_wall(boxes, "e3_workshop_boundary", (-13.0, 4.0), (9.0, 4.0), [(2.0, 1.9), (10.5, 1.35), (19.3, 1.2)], h)
    add_open_wall(boxes, "e3_storage_boundary", (-13.0, -4.0), (9.0, -4.0), [(2.0, 1.9), (10.5, 1.35), (19.3, 1.2)], h)
    # Two rack aisles are deliberately not an empty hall. Their clear aisles
    # remain feasible after inflation and create repeated line-of-sight breaks.
    for i, x in enumerate((-10.0, -4.0, 2.0, 8.0)):
        add_box(boxes, f"e3_workshop_rack_n_{i:02d}", (x, 9.2, 1.4), (3.4, 0.9, 2.8), "brick", "equipment")
        add_box(boxes, f"e3_workshop_rack_s_{i:02d}", (x, 14.2, 1.4), (3.4, 0.9, 2.8), "brick", "equipment")
    add_wall(boxes, "e3_workshop_turn_a", (-12.5, 7.0), (-8.5, 7.0), 2.4, "concrete_light")
    add_wall(boxes, "e3_workshop_turn_b", (4.0, 17.0), (8.5, 17.0), 2.4, "concrete_light")
    # Storage cells are serial with alternating door locations and a partial
    # rear link, unlike E2's balanced three-wing topology.
    for i, x in enumerate((-9.0, -2.0, 5.0)):
        add_open_wall(boxes, f"e3_storage_partition_{i}", (x, -18.8), (x, -4.0), [(4.0 + (i % 2) * 3.0, 1.25 + (i % 2) * 0.2)], h)
    add_open_wall(boxes, "e3_storage_rear_link", (-13.0, -14.2), (9.0, -14.2), [(4.4, 1.3), (15.8, 1.45)], 2.55, "concrete_light")
    add_wall(boxes, "e3_storage_turn_a", (-12.0, -8.0), (-8.0, -8.0), 2.4, "concrete_light")
    add_wall(boxes, "e3_storage_turn_b", (-4.0, -11.2), (-0.5, -11.2), 2.4, "concrete_light")
    # Service wing is an S-shaped loop, reached through two constrained gates.
    add_open_wall(boxes, "e3_service_gate", (9.0, -15.0), (9.0, 15.0), [(6.5, 1.2), (23.5, 1.2)], h)
    add_open_wall(boxes, "e3_service_outer", (18.0, -18.8), (18.0, 18.8), [(8.0, 1.35), (18.8, 1.25), (29.5, 1.35)], h)
    add_open_wall(boxes, "e3_service_north_link", (9.0, 11.0), (23.8, 11.0), [(3.0, 1.35), (10.5, 1.15)], h)
    add_open_wall(boxes, "e3_service_south_link", (9.0, -11.0), (23.8, -11.0), [(3.0, 1.35), (10.5, 1.15)], h)
    for i, (a, b) in enumerate((((10.8, -4.5), (15.0, -4.5)), ((15.0, -4.5), (16.5, 0.0)), ((16.5, 0.0), (13.0, 4.2)), ((13.0, 4.2), (10.5, 1.6)))):
        add_wall(boxes, f"e3_service_core_{i:02d}", a, b, 2.7, "concrete_light")
    add_columns(boxes, "e3_column", [(-12.0, 1.8), (-7.0, -2.0), (-1.0, 2.0), (5.0, -2.0), (-10.5, 15.5), (-2.0, 16.5), (-10.5, -15.5), (-2.0, -16.5), (20.5, 5.8), (20.5, -5.8), (20.5, 14.5)], h)
    add_equipment(boxes, "e3_storage_equipment", [(-11.0, -16.2, 2.3, 0.8, 1.7, 0.0), (-6.5, -6.0, 2.4, 0.8, 1.7, 0.0), (0.0, -15.8, 2.3, 0.8, 1.7, 0.0), (6.8, -6.2, 2.4, 0.8, 1.7, 0.0), (21.0, 14.8, 2.3, 0.9, 1.7, math.pi / 2), (21.0, 0.0, 2.3, 0.9, 1.7, math.pi / 2), (21.0, -14.8, 2.3, 0.9, 1.7, math.pi / 2)])
    add_damage(boxes, "e3_damage", [(-11.0, 16.5, 2.4, 1.0, 1.2, 0.25), (-3.0, 16.5, 2.1, 1.1, 1.2, -0.28), (7.0, 16.0, 2.0, 1.0, 1.15, 0.20), (-11.0, -16.5, 2.4, 1.0, 1.2, -0.25), (-3.0, -16.5, 2.1, 1.1, 1.2, 0.28), (7.0, -16.0, 2.0, 1.0, 1.15, -0.20), (21.0, 8.0, 1.8, 1.2, 1.1, 0.15), (21.0, -8.0, 1.8, 1.2, 1.1, -0.15), (14.5, 7.0, 1.8, 1.0, 1.1, 0.20), (14.5, -7.0, 1.8, 1.0, 1.1, -0.20)])
    add_overhead(boxes, "e3_overhead", [(-11.0, 2.6, 3.8, 0.55, 3.45), (-3.0, -2.6, 3.8, 0.55, 3.45), (-2.0, 11.2, 3.8, 0.55, 3.45), (-2.0, -11.2, 3.8, 0.55, 3.45), (13.5, 6.5, 3.8, 0.55, 3.45), (13.5, -6.5, 3.8, 0.55, 3.45), (20.0, 1.8, 3.6, 0.55, 3.45)])
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


def build_flight_slice_grid(boxes: list[Box], scene: Scene, radius: float, cell=0.20) -> dict:
    """Rasterize collision geometry for offline flight-slice QA only."""
    width, depth, _ = scene.size
    nx, ny = int(width / cell), int(depth / cell)
    blocked = set()
    for iy in range(ny):
        y = -depth / 2 + (iy + 0.5) * cell
        for ix in range(nx):
            x = -width / 2 + (ix + 0.5) * cell
            if any(footprint_contains(x, y, box, radius) for box in boxes):
                blocked.add((ix, iy))
    return {"nx": nx, "ny": ny, "cell": cell, "blocked": blocked}


def cell_for_point(scene: Scene, grid: dict, point) -> tuple[int, int]:
    width, depth, _ = scene.size
    ix = int((point[0] + width / 2) / grid["cell"])
    iy = int((point[1] + depth / 2) / grid["cell"])
    return min(grid["nx"] - 1, max(0, ix)), min(grid["ny"] - 1, max(0, iy))


def flood_distances(grid: dict, source: tuple[int, int]) -> dict:
    """Four-connected grid distances used only to audit the static geometry."""
    if source in grid["blocked"]:
        return {}
    distances, queue = {source: 0}, deque([source])
    while queue:
        ix, iy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = ix + dx, iy + dy
            if 0 <= nxt[0] < grid["nx"] and 0 <= nxt[1] < grid["ny"] and nxt not in grid["blocked"] and nxt not in distances:
                distances[nxt] = distances[(ix, iy)] + 1
                queue.append(nxt)
    return distances


def validate_connectivity(boxes: list[Box], scene: Scene, radius: float, cell=0.20) -> dict:
    """Offline QA: all free cells must be reachable after FUEL-envelope inflation."""
    grid = build_flight_slice_grid(boxes, scene, radius, cell)
    width, depth, _ = scene.size
    nx, ny, blocked = grid["nx"], grid["ny"], grid["blocked"]
    sx, sy = int((scene.entry[0] + width / 2) / cell), int((scene.entry[1] + depth / 2) / cell)
    if (sx, sy) in blocked:
        raise RuntimeError(f"{scene.key}: entry is blocked after planning-envelope inflation")
    seen = flood_distances(grid, (sx, sy))
    free = nx * ny - len(blocked)
    ratio = len(seen) / max(1, free)
    return {
        "passed": ratio >= 0.985,
        "flight_slice_z_m": FLIGHT_SLICE_Z,
        "grid_resolution_m": cell,
        "planning_envelope_radius_m": radius,
        "free_cells": free,
        "reachable_cells": len(seen),
        "reachable_fraction": round(ratio, 6),
        "inflated_occupied_footprint_fraction": round(len(blocked) / float(nx * ny), 6),
    }


def scan_passage_width(scene: Scene, grid: dict, point, longitudinal_axis: str) -> float:
    """Estimate free width orthogonal to a declared passage centerline.

    The probe is a static QA measurement.  It is never exported to Gazebo,
    FUEL, MARSIM or the online cooperative controller.
    """
    origin = cell_for_point(scene, grid, point)
    if origin in grid["blocked"]:
        return 0.0
    dx, dy = (0, 1) if longitudinal_axis == "x" else (1, 0)
    left = right = 0
    for sign in (-1, 1):
        count = 0
        while True:
            candidate = (origin[0] + sign * dx * (count + 1), origin[1] + sign * dy * (count + 1))
            if not (0 <= candidate[0] < grid["nx"] and 0 <= candidate[1] < grid["ny"]) or candidate in grid["blocked"]:
                break
            count += 1
        if sign < 0:
            left = count
        else:
            right = count
    return round((left + right + 1) * grid["cell"], 3)


def audit_scene_contract(boxes: list[Box], scene: Scene, radius: float, cell=0.20) -> dict:
    """Validate declared offline complexity probes against collision geometry.

    The topology graph is an audit artifact that documents the intended static
    test scene.  It is excluded from all runtime assets and is not available to
    any exploration method.
    """
    if not scene.offline_audit:
        return {"available": False}
    physical_grid = build_flight_slice_grid(boxes, scene, 0.0, cell)
    planning_grid = build_flight_slice_grid(boxes, scene, radius, cell)
    entry_cell = cell_for_point(scene, planning_grid, scene.entry)
    entry_distances = flood_distances(planning_grid, entry_cell)
    diameter = 2.0 * radius

    anchors = {}
    for name, point in scene.offline_audit["major_branch_anchors"].items():
        cell_id = cell_for_point(scene, planning_grid, point)
        distance = entry_distances.get(cell_id)
        anchors[name] = {
            "point_xy_m": list(point),
            "free_after_inflation": cell_id not in planning_grid["blocked"],
            "reachable_from_entry": distance is not None,
            "shortest_grid_distance_m": None if distance is None else round(distance * cell, 3),
        }
    branch_distances = [item["shortest_grid_distance_m"] for item in anchors.values() if item["shortest_grid_distance_m"] is not None]
    branch_spread = None
    if branch_distances:
        branch_spread = round((max(branch_distances) - min(branch_distances)) / max(0.001, min(branch_distances)), 6)
    branch_spread_limit = scene.offline_audit.get("branch_distance_max_spread_ratio")
    branch_balance = {
        "interpretation": "offline entry-to-anchor workload proxy; it is never provided to a runtime UAV or allocator",
        "shortest_grid_distance_min_m": None if not branch_distances else min(branch_distances),
        "shortest_grid_distance_max_m": None if not branch_distances else max(branch_distances),
        "relative_spread": branch_spread,
        "maximum_allowed_relative_spread": branch_spread_limit,
        "passed": branch_spread_limit is None or (branch_spread is not None and branch_spread <= branch_spread_limit),
    }

    probes = {}
    for name, point, axis in scene.offline_audit["passage_probes"]:
        physical_width = scan_passage_width(scene, physical_grid, point, axis)
        planning_width = scan_passage_width(scene, planning_grid, point, axis)
        probes[name] = {
            "point_xy_m": list(point),
            "longitudinal_axis": axis,
            "physical_width_m": physical_width,
            "planning_free_width_m": planning_width,
            "physical_width_over_D_eff": None if diameter <= 0 else round(physical_width / diameter, 3),
        }
    ratios = [item["physical_width_over_D_eff"] for item in probes.values() if item["physical_width_over_D_eff"] is not None]
    width_bands = {"<3D_eff": 0, "3D_eff_to_<4D_eff": 0, "4D_eff_to_<5D_eff": 0, ">=5D_eff": 0}
    for ratio in ratios:
        if ratio < 3.0:
            width_bands["<3D_eff"] += 1
        elif ratio < 4.0:
            width_bands["3D_eff_to_<4D_eff"] += 1
        elif ratio < 5.0:
            width_bands["4D_eff_to_<5D_eff"] += 1
        else:
            width_bands[">=5D_eff"] += 1

    contract = scene.offline_audit["topology_graph"]
    node_cells = {name: cell_for_point(scene, planning_grid, point) for name, point in contract["nodes"].items()}
    node_status = {
        name: {
            "point_xy_m": list(contract["nodes"][name]),
            "free_after_inflation": cell_id not in planning_grid["blocked"],
            "reachable_from_entry": cell_id in entry_distances,
        }
        for name, cell_id in node_cells.items()
    }
    degrees = Counter()
    edge_routes = []
    distance_cache = {}
    for left, right in contract["edges"]:
        degrees[left] += 1
        degrees[right] += 1
        if left not in distance_cache:
            distance_cache[left] = flood_distances(planning_grid, node_cells[left])
        steps = distance_cache[left].get(node_cells[right])
        edge_routes.append({"from": left, "to": right, "reachable": steps is not None, "shortest_grid_distance_m": None if steps is None else round(steps * cell, 3)})
    vertices, edges = len(contract["nodes"]), len(contract["edges"])
    graph_summary = {
        "interpretation": "offline declared topology contract with grid-validated nodes and edges; never a runtime navigation graph",
        "node_count": vertices,
        "edge_count": edges,
        "junction_count": sum(1 for degree in degrees.values() if degree >= 3),
        "terminal_count": sum(1 for degree in degrees.values() if degree == 1),
        "cycle_rank": edges - vertices + 1,
        "nodes": node_status,
        "edges": edge_routes,
    }
    passed = (
        all(item["reachable_from_entry"] for item in anchors.values())
        and branch_balance["passed"]
        and all(item["planning_free_width_m"] >= diameter for item in probes.values())
        and all(item["reachable_from_entry"] for item in node_status.values())
        and all(item["reachable"] for item in edge_routes)
    )
    return {
        "available": True,
        "passed": passed,
        "effective_planning_diameter_m": round(diameter, 3),
        "major_branch_count": len(anchors),
        "major_branch_anchors": anchors,
        "branch_workload_balance": branch_balance,
        "passage_probes": probes,
        "passage_width_summary": {
            "interpretation": "static doorway/cross-link throat probes, not a runtime traversability map",
            "probe_count": len(probes),
            "physical_width_min_m": min((item["physical_width_m"] for item in probes.values()), default=None),
            "physical_width_max_m": max((item["physical_width_m"] for item in probes.values()), default=None),
            "count_by_physical_width_over_D_eff": width_bands,
        },
        "declared_topology_graph": graph_summary,
        "physical_occupied_footprint_fraction": round(len(physical_grid["blocked"]) / float(physical_grid["nx"] * physical_grid["ny"]), 6),
        "planning_occupied_footprint_fraction": round(len(planning_grid["blocked"]) / float(planning_grid["nx"] * planning_grid["ny"]), 6),
    }


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
    scene_audit = audit_scene_contract(boxes, scene, radius)
    if scene_audit.get("available") and not scene_audit["passed"]:
        raise RuntimeError(f"{scene.key} rejected by topology/clearance QA: {scene_audit}")
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
        "offline_scene_audit": scene_audit,
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
