"""Regenerate fixed Ruins-Urban-01 runtime assets without replacing repository metadata."""

from __future__ import annotations

import json
import math
import os
import random
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT


def write_text_lf(path: Path, text: str, encoding: str = "ascii"):
    # pathlib.Path.write_text gained its newline argument after Python 3.8.
    with path.open("w", encoding=encoding, newline="\n") as stream:
        stream.write(text)


@dataclass
class Box:
    name: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    material: str = "concrete"
    role: str = "obstacle"


@dataclass
class Variant:
    key: str
    title: str
    seed: int
    rubble_count: int
    column_count: int
    collapsed_wall_count: int
    pcd_step: float
    second_level_extra: bool


VARIANTS = [
    Variant("base", "Ruins-Urban-01 Base", 240701, 28, 6, 8, 0.22, False),
    Variant("medium", "Ruins-Urban-01 Medium", 240702, 52, 10, 15, 0.20, True),
    # This remains a reproducible pre-experiment scene. The paper main scene is
    # the separately frozen challenge variant below.
    Variant("complex", "Ruins-Urban-01 Complexity Pilot", 240703, 78, 14, 24, 0.18, True),
    Variant("challenge", "Ruins-Urban-01 Challenge Ruins", 240704, 128, 22, 42, 0.16, True),
]


PARAMS = {
    "scene_name": "Ruins-Urban-01",
    "units": "meters",
    "dimensions": {"x": 42.0, "y": 32.0, "z": 8.0},
    "origin": "centered_xy_floor_z0",
    "collision_diameter_D": 0.65,
    "min_required_radius": 0.35,
    "corridor_scale_rules": {
        "normal_corridor_width": "max(2.50, 3.8 * D)",
        "narrow_corridor_width": "max(1.35, 2.1 * D)",
        "vertical_connector_width": "max(2.00, 3.1 * D)",
    },
    "corridor_widths": {
        "normal": 2.7,
        "narrow": 1.45,
        "squeeze": 1.22,
        "vertical_connector": 2.2,
    },
    "features": [
        "normal corridors",
        "narrow corridors",
        "forks",
        "loop",
        "dead ends",
        "collapsed wall slabs",
        "rubble fields",
        "columns",
        "partial second level",
        "multiple vertical connectors",
        "low-overhead passages",
        "forced altitude-change gates",
        "repetitive and low-feature geometry",
        "breached room shells and irregular collapse clusters",
    ],
}


MATERIALS = {
    "concrete": (0.58, 0.56, 0.52),
    "concrete_light": (0.68, 0.66, 0.61),
    "dark_concrete": (0.35, 0.35, 0.34),
    "rebar": (0.12, 0.12, 0.12),
    "rubble": (0.46, 0.42, 0.36),
    "brick": (0.43, 0.29, 0.23),
    "soil": (0.29, 0.25, 0.20),
    "rust": (0.37, 0.20, 0.13),
    "hazard": (0.65, 0.18, 0.12),
}


LOWER_NAV_NODES = {
    "entry": (-19.2, 0.0, 1.35),
    "g1": (-16.0, 0.0, 1.35),
    "g2": (-12.0, -0.8, 1.35),
    "g3": (-8.0, 0.6, 1.35),
    "g4": (-3.5, -0.4, 1.55),
    "g5": (1.5, 0.8, 1.20),
    "g6": (6.5, -0.3, 1.60),
    "g7": (11.5, 0.9, 1.35),
    "g8": (16.0, 0.0, 1.35),
    "east_terminal": (19.0, 1.0, 1.35),
    "n1": (-13.0, 4.8, 1.35),
    "n2": (-15.0, 9.0, 1.35),
    "n3": (-11.5, 13.0, 1.35),
    "n4": (-6.5, 11.5, 1.35),
    "n5": (-4.0, 7.0, 1.35),
    "dead_nw": (-18.3, 13.0, 1.35),
    "s1": (-9.0, -4.8, 1.35),
    "s2": (-14.0, -7.5, 1.35),
    "s3": (-15.0, -12.0, 1.35),
    "s4": (-8.0, -13.0, 1.35),
    "s5": (-2.5, -10.0, 1.35),
    "s6": (1.5, -6.0, 1.35),
    "dead_sw": (-19.0, -10.5, 1.35),
    "en1": (13.0, 5.0, 1.35),
    "en2": (17.0, 7.0, 1.35),
    "dead_ne": (18.0, 12.5, 1.35),
    "es1": (12.5, -4.8, 1.35),
    "es2": (16.0, -8.5, 1.35),
    "dead_se": (19.0, -13.0, 1.35),
    "center_south": (6.0, -7.5, 1.35),
}

UPPER_NAV_NODES = {
    "ua": (-4.0, 7.0, 4.55),
    "u1": (1.0, 10.5, 4.55),
    "u2": (7.0, 11.0, 4.55),
    "u3": (11.0, 7.5, 4.55),
    "u4": (9.0, 3.0, 4.55),
    "uc": (1.5, 0.8, 4.55),
    "u5": (6.0, -3.0, 4.55),
    "u6": (11.0, -5.5, 4.55),
    "ub": (16.0, -8.5, 4.55),
    "upper_dead": (16.0, 3.0, 4.55),
    # Challenge-only upper network. These are generation-time QA centerlines,
    # never task partitions exposed to any UAV.
    "us3": (-15.0, -12.0, 4.55),
    "us4": (-8.0, -13.0, 4.55),
    "us5": (-2.5, -10.0, 4.55),
    "us6": (1.5, -6.0, 4.55),
    "us7": (6.0, -7.5, 4.55),
    "upper_south_dead": (12.0, -12.0, 4.55),
}

GROUND_BASE_EDGES = [
    ("entry", "g1"),
    ("g1", "g2"),
    ("g2", "g3"),
    ("g3", "g4"),
    ("g4", "g5"),
    ("g5", "g6"),
    ("g6", "g7"),
    ("g7", "g8"),
    ("g8", "east_terminal"),
    ("g2", "n1"),
    ("n1", "n2"),
    ("n2", "n3"),
    ("n3", "n4"),
    ("n4", "n5"),
    ("n5", "g4"),
    ("n2", "dead_nw"),
    ("g3", "s1"),
    ("s1", "s2"),
    ("s2", "s3"),
    ("s3", "s4"),
    ("s4", "s5"),
    ("s5", "s6"),
    ("s6", "g5"),
    ("s2", "dead_sw"),
]

GROUND_EXTENDED_EDGES = [
    ("g7", "en1"),
    ("en1", "en2"),
    ("en2", "dead_ne"),
    ("g7", "es1"),
    ("es1", "es2"),
    ("es2", "dead_se"),
    ("es1", "center_south"),
    ("center_south", "s6"),
]

UPPER_MEDIUM_EDGES = [
    ("n5", "ua"),
    ("ua", "u1"),
    ("u1", "u2"),
    ("u2", "u3"),
    ("u3", "u4"),
    ("u4", "uc"),
    ("uc", "ua"),
    ("g5", "uc"),
]

UPPER_COMPLEX_EDGES = [
    ("uc", "u5"),
    ("u5", "u6"),
    ("u6", "ub"),
    ("es2", "ub"),
    ("u3", "upper_dead"),
]

UPPER_CHALLENGE_EDGES = [
    ("s3", "us3"),
    ("s5", "us5"),
    ("center_south", "us7"),
    ("us3", "us4"),
    ("us4", "us5"),
    ("us5", "us6"),
    ("us6", "us7"),
    ("us5", "uc"),
    ("us7", "ub"),
    ("us7", "upper_south_dead"),
]

def navigation_graph(variant: Variant):
    nodes = {**LOWER_NAV_NODES, **UPPER_NAV_NODES}
    edges = list(GROUND_BASE_EDGES)
    if variant.key in {"medium", "complex"}:
        edges += GROUND_EXTENDED_EDGES + UPPER_MEDIUM_EDGES
    if variant.key == "complex":
        edges += UPPER_COMPLEX_EDGES
    if variant.key == "challenge":
        edges += GROUND_EXTENDED_EDGES + UPPER_MEDIUM_EDGES + UPPER_COMPLEX_EDGES + UPPER_CHALLENGE_EDGES
    used = {name for edge in edges for name in edge}
    return {name: nodes[name] for name in sorted(used)}, edges


def rot_matrix(rpy: tuple[float, float, float]) -> list[list[float]]:
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def mat_vec(m: list[list[float]], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def box_vertices(box: Box) -> list[tuple[float, float, float]]:
    sx, sy, sz = box.size
    corners = [
        (-sx / 2, -sy / 2, -sz / 2),
        (sx / 2, -sy / 2, -sz / 2),
        (sx / 2, sy / 2, -sz / 2),
        (-sx / 2, sy / 2, -sz / 2),
        (-sx / 2, -sy / 2, sz / 2),
        (sx / 2, -sy / 2, sz / 2),
        (sx / 2, sy / 2, sz / 2),
        (-sx / 2, sy / 2, sz / 2),
    ]
    r = rot_matrix(box.rpy)
    return [add(box.center, mat_vec(r, c)) for c in corners]


FACES = [
    (1, 2, 3, 4),
    (5, 8, 7, 6),
    (1, 5, 6, 2),
    (2, 6, 7, 3),
    (3, 7, 8, 4),
    (4, 8, 5, 1),
]


def add_box(boxes: list[Box], name: str, center, size, rpy=(0.0, 0.0, 0.0), material="concrete", role="obstacle"):
    boxes.append(Box(name, tuple(center), tuple(size), tuple(rpy), material, role))


def add_wall(boxes: list[Box], name: str, p0, p1, height=3.2, thickness=0.34, z=1.6, material="concrete"):
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    add_box(boxes, name, ((x0 + x1) / 2, (y0 + y1) / 2, z), (length, thickness, height), (0.0, 0.0, yaw), material)


def dist_point_to_segment_xy(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy)


def near_navigation_xy(x, y, variant: Variant, margin=1.45):
    nodes, edges = navigation_graph(variant)
    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        if dist_point_to_segment_xy((x, y), (pa[0], pa[1]), (pb[0], pb[1])) < margin:
            return True
    return False


def add_corridor_walls(
    boxes: list[Box],
    name: str,
    p0,
    p1,
    width: float,
    height: float = 2.9,
    z: float | None = None,
    thickness: float = 0.30,
    end_gap: float = 1.15,
    material: str = "concrete",
):
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length <= 2 * end_gap + 0.2:
        return
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    ax, ay = x0 + ux * end_gap, y0 + uy * end_gap
    bx, by = x1 - ux * end_gap, y1 - uy * end_gap
    wall_z = z if z is not None else height / 2
    offset = width / 2 + thickness / 2
    for side, sign in (("left", 1.0), ("right", -1.0)):
        add_wall(
            boxes,
            f"{name}_{side}",
            (ax + nx * offset * sign, ay + ny * offset * sign),
            (bx + nx * offset * sign, by + ny * offset * sign),
            height=height,
            thickness=thickness,
            z=wall_z,
            material=material,
        )


def add_segment_box(boxes: list[Box], name: str, p0, p1, width: float, thickness: float, z: float, material: str, role: str):
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    add_box(
        boxes,
        name,
        ((x0 + x1) / 2, (y0 + y1) / 2, z),
        (length, width, thickness),
        (0.0, 0.0, yaw),
        material,
        role,
    )


def add_upper_network(boxes: list[Box], variant: Variant):
    nodes, edges = navigation_graph(variant)
    degree = {name: 0 for name in nodes}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    upper_edges = []
    active_connectors = []
    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        if abs(pa[2] - pb[2]) > 0.8:
            low, high = (pa, pb) if pa[2] < pb[2] else (pb, pa)
            active_connectors.append((f"connector_{len(active_connectors) + 1:02d}", low, high))
    connector_nodes = {name for _, low, high in active_connectors for name, point in nodes.items() if point in {low, high}}
    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        if abs(pa[2] - pb[2]) > 0.8:
            continue
        if pa[2] < 4.0 or pb[2] < 4.0:
            continue
        upper_edges.append((a, b))
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        length = math.hypot(dx, dy)
        shorten = min(1.05, max(0.0, length / 2 - 0.25))
        ux, uy = dx / length, dy / length
        p0 = (pa[0] + ux * shorten, pa[1] + uy * shorten)
        p1 = (pb[0] - ux * shorten, pb[1] - uy * shorten)
        add_segment_box(
            boxes,
            f"upper_walkway_{a}_{b}",
            p0,
            p1,
            2.45,
            0.24,
            3.36,
            "dark_concrete",
            "upper_floor",
        )
        if variant.key != "challenge":
            add_corridor_walls(
                boxes,
                f"upper_corridor_{a}_{b}",
                pa,
                pb,
                width=2.25,
                height=2.0,
                z=4.38,
                thickness=0.22,
                # Junctions need a larger open volume so walls from one upper
                # corridor cannot intrude into a crossing connector or branch.
                end_gap=2.15 if degree[a] >= 3 or degree[b] >= 3 else 1.35,
                material="concrete_light",
            )

    used_upper_nodes = {n for edge in upper_edges for n in edge}
    for name in sorted(used_upper_nodes - connector_nodes):
        p = nodes[name]
        add_box(
            boxes,
            f"upper_node_platform_{name}",
            (p[0], p[1], 3.36),
            (2.5, 2.5, 0.24),
            material="dark_concrete",
            role="upper_floor",
        )

    # Open connector shafts are framed but intentionally have no slab at the center.
    for name, low, high in active_connectors:
        x, y = high[0], high[1]
        for idx, (ox, oy, sx, sy) in enumerate(
            [
                (-1.35, 0.0, 0.22, 2.7),
                (1.35, 0.0, 0.22, 2.7),
                (0.0, -1.35, 2.7, 0.22),
                (0.0, 1.35, 2.7, 0.22),
            ]
        ):
            # Leave one side open at flight level to avoid making a closed cage.
            if idx == 2:
                continue
            add_box(
                boxes,
                f"{name}_frame_{idx}",
                (x + ox, y + oy, 3.55),
                (sx, sy, 0.42),
                material="rust",
                role="connector_frame",
            )


def base_structure(variant: Variant) -> list[Box]:
    if variant.key == "challenge":
        return challenge_structure(variant)
    boxes: list[Box] = []
    add_box(boxes, "floor_slab", (0, 0, -0.08), (42.0, 32.0, 0.16), material="dark_concrete", role="floor")
    # Broken, uneven perimeter: the west wall contains the only initial opening.
    add_box(boxes, "north_boundary_west", (-11.5, 15.85, 1.55), (19.0, 0.38, 3.1), (0.0, 0.0, -0.01))
    add_box(boxes, "north_boundary_east", (10.5, 15.9, 1.80), (21.0, 0.42, 3.6), (0.0, 0.0, 0.015))
    add_box(boxes, "south_boundary_west", (-10.0, -15.9, 1.75), (22.0, 0.42, 3.5), (0.0, 0.0, 0.012))
    add_box(boxes, "south_boundary_east", (12.0, -15.85, 1.50), (18.0, 0.38, 3.0), (0.0, 0.0, -0.018))
    add_box(boxes, "west_boundary_north", (-20.95, 9.15, 1.70), (0.42, 13.7, 3.4), (0.0, 0.0, -0.02))
    add_box(boxes, "west_boundary_south", (-20.95, -9.15, 1.70), (0.42, 13.7, 3.4), (0.0, 0.0, 0.015))
    add_box(boxes, "east_boundary", (20.95, 0.0, 1.7), (0.42, 31.8, 3.4), (0.0, 0.0, -0.01))

    nodes, edges = navigation_graph(variant)
    degree = {name: 0 for name in nodes}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    narrow_edges = {
        ("n1", "n2"), ("n3", "n4"), ("s1", "s2"), ("s3", "s4"),
        ("en1", "en2"), ("es1", "es2"), ("u2", "u3"), ("u5", "u6"),
    }
    squeeze_edges = {("n4", "n5"), ("s4", "s5"), ("en2", "dead_ne"), ("u6", "ub")}
    enclosed_edges = {
        ("g2", "n1"), ("n1", "n2"), ("n2", "n3"), ("n3", "n4"), ("n4", "n5"),
        ("g3", "s1"), ("s1", "s2"), ("s2", "s3"), ("s3", "s4"), ("s4", "s5"),
        ("g7", "en1"), ("en1", "en2"), ("en2", "dead_ne"),
        ("g7", "es1"), ("es1", "es2"), ("es2", "dead_se"),
    }
    for a, b in edges:
        if (a, b) not in enclosed_edges:
            continue
        width = 2.7
        if (a, b) in narrow_edges:
            width = 1.45
        if (a, b) in squeeze_edges and variant.key == "complex":
            width = 1.22
        add_corridor_walls(
            boxes,
            f"ground_corridor_{a}_{b}",
            nodes[a],
            nodes[b],
            width=width,
            height=2.75 if width < 2.0 else 3.15,
            thickness=0.28,
            end_gap=2.25 if "s2" in {a, b} else 1.75,
            material="concrete",
        )

    # Irregular main spine with staggered wall panels and door-sized gaps.
    spine_panels = [
        ((-18.6, 2.25), (-15.5, 2.15)), ((-13.8, 1.75), (-10.7, 1.55)),
        ((-9.2, 2.45), (-6.3, 2.65)), ((-4.8, 1.75), (-1.8, 2.05)),
        ((-0.4, 2.65), (2.1, 2.45)), ((3.8, 1.95), (6.2, 2.15)),
        ((7.7, 2.60), (10.1, 2.35)), ((12.8, 2.10), (15.4, 2.25)),
        ((-18.3, -2.30), (-15.2, -2.15)), ((-13.5, -2.75), (-10.8, -2.45)),
        ((-9.0, -1.75), (-6.2, -2.05)), ((-4.7, -2.80), (-2.0, -2.55)),
        ((-0.1, -1.65), (2.5, -1.85)), ((4.0, -2.75), (6.6, -2.45)),
        ((8.0, -1.60), (10.4, -1.75)), ((13.0, -2.55), (16.0, -2.30)),
    ]
    branch_openings = {1, 3, 10, 12}
    for idx, (p0, p1) in enumerate(spine_panels):
        if idx in branch_openings:
            continue
        height = 2.6 + 0.25 * (idx % 3)
        add_wall(boxes, f"spine_broken_panel_{idx:02d}", p0, p1, height=height, thickness=0.30, z=height / 2)

    # A low-feature utility tunnel and a repetitive column hall create perception aliasing.
    add_box(boxes, "utility_ceiling_01", (-13.8, 8.0, 2.72), (6.5, 3.0, 0.28), (0.0, 0.0, -0.45), "dark_concrete", "ceiling")
    add_box(boxes, "utility_ceiling_02", (-10.0, 12.1, 2.62), (5.0, 2.6, 0.26), (0.0, 0.0, -0.28), "dark_concrete", "ceiling")
    fixed_pillars = [
        (-17.2, 6.0), (-17.2, 8.4), (-17.2, 10.8),
        (8.6, 6.0), (11.0, 6.0), (13.4, 6.0),
        (8.6, 9.0), (11.0, 9.0), (13.4, 9.0),
        (-1.0, -12.8), (3.0, -10.5), (8.5, -11.8),
    ]
    for idx, (x, y) in enumerate(fixed_pillars):
        if near_navigation_xy(x, y, variant, margin=1.05):
            continue
        add_box(boxes, f"fixed_column_{idx:02d}", (x, y, 1.75), (0.62, 0.62, 3.5), material="concrete_light")

    # Deterministic 3D gates force vertical maneuvering instead of planar flight.
    add_box(boxes, "overflight_rubble_gate", (-1.2, 0.35, 0.45), (1.25, 2.2, 0.90), (0.05, -0.06, -0.18), "rubble")
    add_box(boxes, "underflight_hanging_gate", (4.0, 0.25, 2.55), (1.2, 2.4, 1.05), (-0.04, 0.08, -0.20), "dark_concrete")
    add_box(boxes, "east_slanted_beam", (9.2, 0.55, 2.85), (4.8, 0.34, 0.34), (0.0, 0.10, 0.22), "rust")

    if variant.key in {"medium", "complex", "challenge"}:
        add_upper_network(boxes, variant)
    return boxes


def challenge_structure(variant: Variant) -> list[Box]:
    """Build the frozen paper main scene as a damaged urban underground layout.

    The reference graph is used exclusively for collision-clearance validation.
    It is deliberately not serialized into any runtime planning input.
    """
    boxes: list[Box] = []
    add_box(boxes, "challenge_floor_slab", (0.0, 0.0, -0.10), (42.0, 32.0, 0.20), material="dark_concrete", role="floor")

    # Perimeter segments retain a single broad western entrance, while varied
    # heights and slight rotations avoid the appearance of a clean office box.
    boundary_segments = [
        ("north_a", (-14.5, 15.78), (-2.8, 15.72), 3.4),
        ("north_b", (-1.7, 15.80), (9.4, 15.86), 2.8),
        ("north_c", (10.5, 15.76), (20.8, 15.82), 3.7),
        ("south_a", (-20.8, -15.82), (-8.5, -15.74), 3.5),
        ("south_b", (-7.2, -15.84), (4.0, -15.78), 2.9),
        ("south_c", (5.0, -15.76), (20.8, -15.84), 3.6),
        ("west_n", (-20.84, 15.75), (-20.90, 2.2), 3.4),
        ("west_s", (-20.88, -2.2), (-20.82, -15.75), 3.2),
        ("east_a", (20.84, -15.7), (20.92, -1.5), 3.3),
        ("east_b", (20.86, -0.3), (20.90, 15.7), 3.8),
    ]
    for idx, (name, p0, p1, height) in enumerate(boundary_segments):
        add_wall(
            boxes,
            f"challenge_boundary_{name}",
            p0,
            p1,
            height=height,
            thickness=0.42,
            z=height / 2,
            material="concrete" if idx % 3 else "concrete_light",
        )

    nodes, edges = navigation_graph(variant)
    degree = {name: 0 for name in nodes}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    narrow_edges = {
        ("n1", "n2"), ("n3", "n4"), ("s1", "s2"), ("s3", "s4"),
        ("en1", "en2"), ("es1", "es2"), ("u2", "u3"), ("u5", "u6"),
        ("us3", "us4"), ("us4", "us5"), ("us6", "us7"),
    }
    squeeze_edges = {
        ("n4", "n5"), ("s4", "s5"), ("en2", "dead_ne"),
        ("u6", "ub"), ("us7", "upper_south_dead"),
    }
    main_spine = {
        ("entry", "g1"), ("g1", "g2"), ("g2", "g3"), ("g3", "g4"),
        ("g4", "g5"), ("g5", "g6"), ("g6", "g7"), ("g7", "g8"),
    }
    for idx, (a, b) in enumerate(edges):
        pa, pb = nodes[a], nodes[b]
        if abs(pa[2] - pb[2]) > 0.8 or pa[2] > 3.5 or pb[2] > 3.5:
            continue
        width = 3.20 if (a, b) in main_spine else 2.55
        if (a, b) in narrow_edges:
            width = 1.45
        if (a, b) in squeeze_edges:
            width = 1.22
        height = 2.55 + 0.20 * (idx % 4)
        add_corridor_walls(
            boxes,
            f"challenge_ground_corridor_{a}_{b}",
            pa,
            pb,
            width=width,
            height=height,
            thickness=0.30,
            end_gap=2.35 if degree[a] >= 3 or degree[b] >= 3 else 1.55,
            material="concrete" if idx % 2 else "concrete_light",
        )

    # Distinct damaged structures make the space a ruin rather than a regular maze.
    rng = random.Random(variant.seed + 91)
    clusters = 0
    attempts = 0
    while clusters < 11 and attempts < 4000:
        attempts += 1
        x = rng.uniform(-17.5, 17.5)
        y = rng.uniform(-13.0, 13.0)
        if near_navigation_xy(x, y, variant, margin=3.1):
            continue
        yaw = rng.uniform(0.0, math.pi)
        facade_len = rng.uniform(3.4, 5.8)
        facade_h = rng.uniform(2.4, 4.8)
        add_box(
            boxes,
            f"challenge_broken_facade_{clusters:02d}",
            (x, y, facade_h / 2),
            (facade_len, 0.34, facade_h),
            (rng.uniform(-0.18, 0.18), rng.uniform(-0.22, 0.22), yaw),
            "concrete_light",
            "collapsed_facade",
        )
        add_box(
            boxes,
            f"challenge_fallen_slab_{clusters:02d}",
            (x + rng.uniform(-1.0, 1.0), y + rng.uniform(-1.0, 1.0), rng.uniform(0.65, 1.25)),
            (rng.uniform(2.4, 4.6), rng.uniform(0.70, 1.35), 0.34),
            (rng.uniform(-0.30, 0.30), rng.uniform(-0.30, 0.30), yaw + rng.uniform(-0.55, 0.55)),
            "rubble",
            "collapsed_slab",
        )
        for piece in range(3):
            sx, sy, sz = rng.uniform(0.45, 1.35), rng.uniform(0.35, 1.10), rng.uniform(0.30, 0.95)
            add_box(
                boxes,
                f"challenge_cluster_{clusters:02d}_rubble_{piece}",
                (x + rng.uniform(-2.0, 2.0), y + rng.uniform(-2.0, 2.0), sz / 2),
                (sx, sy, sz),
                (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), rng.uniform(0.0, math.pi)),
                "brick" if piece == 0 else "rubble",
                "rubble",
            )
        clusters += 1

    # Overhead debris makes the upper structure visually and geometrically distinct.
    beams = 0
    attempts = 0
    while beams < 18 and attempts < 5000:
        attempts += 1
        x = rng.uniform(-18.0, 18.0)
        y = rng.uniform(-14.0, 14.0)
        if near_navigation_xy(x, y, variant, margin=1.45):
            continue
        length = rng.uniform(2.0, 5.2)
        add_box(
            boxes,
            f"challenge_hanging_beam_{beams:02d}",
            (x, y, rng.uniform(4.95, 6.20)),
            (length, rng.uniform(0.14, 0.32), rng.uniform(0.16, 0.34)),
            (rng.uniform(-0.24, 0.24), rng.uniform(-0.42, 0.42), rng.uniform(0.0, math.pi)),
            "rust",
            "hanging_debris",
        )
        beams += 1

    # The upper network provides six actual altitude transitions, not just high decorations.
    add_upper_network(boxes, variant)
    return boxes


def add_variant_obstacles(boxes: list[Box], variant: Variant):
    rng = random.Random(variant.seed)

    # Random columns are kept away from validated centerlines.
    placed = 0
    attempts = 0
    while placed < variant.column_count and attempts < 2000:
        attempts += 1
        x = rng.uniform(-18.5, 18.5)
        y = rng.uniform(-13.5, 13.5)
        h = rng.uniform(2.4, 4.0)
        sx = rng.uniform(0.45, 0.85)
        sy = rng.uniform(0.45, 0.9)
        if near_navigation_xy(x, y, variant, margin=math.hypot(sx, sy) / 2 + 0.48):
            continue
        add_box(boxes, f"{variant.key}_random_column_{placed:02d}", (x, y, h / 2), (sx, sy, h), material="concrete")
        placed += 1

    # Rubble blocks are low but dense; a few are near paths without closing them.
    placed = 0
    attempts = 0
    while placed < variant.rubble_count and attempts < 5000:
        attempts += 1
        x = rng.uniform(-19.0, 19.0)
        y = rng.uniform(-14.0, 14.0)
        sx = rng.uniform(0.35, 1.65)
        sy = rng.uniform(0.30, 1.35)
        sz = rng.uniform(0.18, 1.15)
        margin = math.hypot(sx, sy) / 2 + (0.40 if placed % 6 == 0 else 0.52)
        if near_navigation_xy(x, y, variant, margin=margin):
            continue
        roll = rng.uniform(-0.18, 0.18)
        pitch = rng.uniform(-0.18, 0.18)
        yaw = rng.uniform(0.0, math.pi)
        material = "brick" if placed % 4 == 0 else ("soil" if placed % 7 == 0 else "rubble")
        add_box(boxes, f"{variant.key}_rubble_{placed:03d}", (x, y, sz / 2), (sx, sy, sz), (roll, pitch, yaw), material)
        placed += 1

    # Collapsed wall slabs are tilted in mesh/PCD and visually separate from standing walls.
    placed = 0
    attempts = 0
    while placed < variant.collapsed_wall_count and attempts < 3000:
        attempts += 1
        x = rng.uniform(-18.0, 18.0)
        y = rng.uniform(-13.0, 13.0)
        length = rng.uniform(2.0, 4.8)
        width = rng.uniform(0.30, 0.55)
        height = rng.uniform(0.35, 0.85)
        if near_navigation_xy(x, y, variant, margin=math.hypot(length, width) / 2 + 0.48):
            continue
        roll = rng.uniform(-0.15, 0.15)
        pitch = rng.uniform(-0.18, 0.18)
        yaw = rng.uniform(0.0, math.pi)
        add_box(
            boxes,
            f"{variant.key}_collapsed_wall_{placed:02d}",
            (x, y, height / 2 + rng.uniform(0.0, 0.25)),
            (length, width, height),
            (roll, pitch, yaw),
            "rubble",
        )
        placed += 1

    if variant.second_level_extra:
        add_box(boxes, f"{variant.key}_broken_upper_slab_01", (3.5, 11.7, 5.7), (4.8, 0.8, 0.34), (0.08, -0.22, 0.12), "rubble")
        add_box(boxes, f"{variant.key}_broken_upper_slab_02", (10.2, 3.8, 5.5), (3.6, 0.75, 0.30), (-0.10, 0.18, -0.40), "rubble")
        add_wall(boxes, f"{variant.key}_narrow_deflector_01", (-6.0, -5.2), (-3.2, -4.6), height=2.6, thickness=0.28)
        add_wall(boxes, f"{variant.key}_narrow_deflector_02", (6.8, 3.9), (8.7, 5.8), height=2.5, thickness=0.28)
    if variant.key in {"complex", "challenge"}:
        add_wall(boxes, "complex_dead_end_internal_01", (2.8, 4.8), (5.3, 4.5), height=3.0, thickness=0.32)
        add_wall(boxes, "complex_dead_end_internal_02", (5.3, 4.5), (5.5, 7.2), height=2.8, thickness=0.32)
        add_wall(boxes, "complex_lower_chicane_01", (-18.0, -5.0), (-15.2, -5.5), height=2.7, thickness=0.28)
        add_wall(boxes, "complex_lower_chicane_02", (-12.8, -10.0), (-9.2, -10.6), height=2.7, thickness=0.28)
        # Hanging debris and exposed rebar add vertical occlusion without sealing routes.
        for idx in range(14):
            x = rng.uniform(-17.5, 17.5)
            y = rng.uniform(-13.5, 13.5)
            length = rng.uniform(1.2, 3.8)
            if near_navigation_xy(x, y, variant, margin=length / 2 + 0.45):
                continue
            add_box(
                boxes,
                f"complex_hanging_beam_{idx:02d}",
                (x, y, rng.uniform(2.4, 5.8)),
                (length, rng.uniform(0.12, 0.28), rng.uniform(0.12, 0.30)),
                (rng.uniform(-0.2, 0.2), rng.uniform(-0.4, 0.4), rng.uniform(0.0, math.pi)),
                "rust",
            )
        for idx in range(18):
            x = rng.uniform(-18.0, 18.0)
            y = rng.uniform(-14.0, 14.0)
            length = rng.uniform(1.0, 2.8)
            if near_navigation_xy(x, y, variant, margin=length / 2 + 0.42):
                continue
            add_box(
                boxes,
                f"complex_rebar_{idx:02d}",
                (x, y, rng.uniform(0.8, 2.0)),
                (length, 0.08, 0.08),
                (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0.0, math.pi)),
                "rebar",
            )


def make_scene(variant: Variant) -> list[Box]:
    boxes = base_structure(variant)
    add_variant_obstacles(boxes, variant)
    return boxes


def iter_surface_points(box: Box, step: float) -> Iterable[tuple[float, float, float]]:
    sx, sy, sz = box.size
    r = rot_matrix(box.rpy)
    faces = [
        ("x", -sx / 2, sy, sz),
        ("x", sx / 2, sy, sz),
        ("y", -sy / 2, sx, sz),
        ("y", sy / 2, sx, sz),
        ("z", -sz / 2, sx, sy),
        ("z", sz / 2, sx, sy),
    ]
    for axis, const, a_len, b_len in faces:
        na = max(1, int(math.ceil(a_len / step)))
        nb = max(1, int(math.ceil(b_len / step)))
        for ia in range(na + 1):
            a = -a_len / 2 + a_len * ia / na
            for ib in range(nb + 1):
                b = -b_len / 2 + b_len * ib / nb
                if axis == "x":
                    local = (const, a, b)
                elif axis == "y":
                    local = (a, const, b)
                else:
                    local = (a, b, const)
                yield add(box.center, mat_vec(r, local))


def write_pcd(path: Path, boxes: list[Box], step: float):
    points = []
    seen = set()
    for box in boxes:
        if box.role in {"connector_marker"}:
            continue
        for p in iter_surface_points(box, step):
            q = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
            key = (int(q[0] * 1000), int(q[1] * 1000), int(q[2] * 1000))
            if key not in seen:
                seen.add(key)
                points.append(q)
    with path.open("w", encoding="ascii", newline="\n") as f:
        f.write("# .PCD v0.7 - Point Cloud Data file format\n")
        f.write("VERSION 0.7\n")
        f.write("FIELDS x y z\n")
        f.write("SIZE 4 4 4\n")
        f.write("TYPE F F F\n")
        f.write("COUNT 1 1 1\n")
        f.write(f"WIDTH {len(points)}\n")
        f.write("HEIGHT 1\n")
        f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
        f.write(f"POINTS {len(points)}\n")
        f.write("DATA ascii\n")
        for p in points:
            f.write(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\n")
    return len(points)


def write_obj(path: Path, boxes: list[Box], mtl_name: str):
    with path.open("w", encoding="ascii", newline="\n") as f:
        f.write(f"mtllib {mtl_name}\n")
        vertex_offset = 0
        for box in boxes:
            verts = box_vertices(box)
            f.write(f"o {box.name}\n")
            f.write(f"usemtl {box.material}\n")
            for v in verts:
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
            for face in FACES:
                ids = [str(vertex_offset + i) for i in face]
                f.write("f " + " ".join(ids) + "\n")
            vertex_offset += 8


def write_mtl(path: Path):
    with path.open("w", encoding="ascii", newline="\n") as f:
        materials = list(MATERIALS.items())
        for index, (name, rgb) in enumerate(materials):
            f.write(f"newmtl {name}\n")
            f.write(f"Kd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\n")
            f.write("Ka 0.050 0.050 0.050\n")
            f.write("Ks 0.020 0.020 0.020\n")
            f.write("d 1.0\n")
            if index + 1 < len(materials):
                f.write("\n")


def write_dae(path: Path, boxes: list[Box]):
    vertices: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    for box in boxes:
        offset = len(vertices)
        vertices.extend(box_vertices(box))
        for face in FACES:
            a, b, c, d = [offset + i - 1 for i in face]
            tris.append((a, b, c))
            tris.append((a, c, d))
    positions = " ".join(f"{v[0]:.5f} {v[1]:.5f} {v[2]:.5f}" for v in vertices)
    indices = " ".join(" ".join(str(i) for i in tri) for tri in tris)
    dae = f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>
  <library_geometries>
    <geometry id="ruins_urban_01_geometry" name="Ruins-Urban-01">
      <mesh>
        <source id="positions">
          <float_array id="positions-array" count="{len(vertices) * 3}">{positions}</float_array>
          <technique_common>
            <accessor source="#positions-array" count="{len(vertices)}" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="vertices"><input semantic="POSITION" source="#positions"/></vertices>
        <triangles count="{len(tris)}">
          <input semantic="VERTEX" source="#vertices" offset="0"/>
          <p>{indices}</p>
        </triangles>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="Ruins-Urban-01" name="Ruins-Urban-01">
        <instance_geometry url="#ruins_urban_01_geometry"/>
      </node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#Scene"/></scene>
</COLLADA>
"""
    write_text_lf(path, dae)


def xml_pose(center: tuple[float, float, float], rpy: tuple[float, float, float]) -> str:
    return f"{center[0]:.5f} {center[1]:.5f} {center[2]:.5f} {rpy[0]:.5f} {rpy[1]:.5f} {rpy[2]:.5f}"


def xml_size(size: tuple[float, float, float]) -> str:
    return f"{size[0]:.5f} {size[1]:.5f} {size[2]:.5f}"


def sdf_material(material: str) -> str:
    rgb = MATERIALS.get(material, MATERIALS["concrete"])
    rgba = f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} 1"
    return f"""
          <material>
            <ambient>{rgba}</ambient>
            <diffuse>{rgba}</diffuse>
            <specular>0.03 0.03 0.03 1</specular>
          </material>"""


def write_model_files(model_dir: Path, variant: Variant, boxes: list[Box], asset_key: str | None = None):
    model_name = f"ruins_urban_01_{asset_key or variant.key}"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "meshes").mkdir(exist_ok=True)
    links = []
    for idx, box in enumerate(boxes):
        # Gazebo Classic is more reliable with primitive boxes than with a large
        # custom Collada collision mesh. Keep DAE/OBJ exports for Blender and
        # other tools, but make Gazebo load native SDF geometry.
        link_name = f"{idx:03d}_{box.name}"
        links.append(f"""    <link name="{link_name}">
      <pose>{xml_pose(box.center, box.rpy)}</pose>
      <visual name="visual">
        <geometry>
          <box><size>{xml_size(box.size)}</size></box>
        </geometry>{sdf_material(box.material)}
      </visual>
      <collision name="collision">
        <geometry>
          <box><size>{xml_size(box.size)}</size></box>
        </geometry>
        <surface>
          <contact><collide_bitmask>0x01</collide_bitmask></contact>
          <friction>
            <ode><mu>1.0</mu><mu2>1.0</mu2></ode>
          </friction>
        </surface>
      </collision>
    </link>""")
    joined_links = "\n".join(links)
    sdf = f"""<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{model_name}">
    <static>true</static>
{joined_links}
  </model>
</sdf>
"""
    config = f"""<?xml version="1.0" ?>
<model>
  <name>{model_name}</name>
  <version>1.0</version>
  <sdf version="1.6">model.sdf</sdf>
  <author>
    <name>Codex generated</name>
  </author>
  <description>Ruins-Urban-01 {variant.key} rubble exploration environment.</description>
</model>
"""
    write_text_lf(model_dir / "model.sdf", sdf)
    write_text_lf(model_dir / "model.config", config)


def write_world(
    path: Path,
    variant: Variant,
    fog_enabled: bool = False,
    world_label: str | None = None,
    model_key: str | None = None,
):
    model_name = f"ruins_urban_01_{model_key or variant.key}"
    if fog_enabled:
        ambient = "0.28 0.27 0.25 1"
        background = "0.25 0.25 0.26 1"
        fog = """
      <fog><type>linear</type><color>0.30 0.29 0.27 1</color><start>7</start><end>34</end><density>0.008</density></fog>"""
    elif variant.key == "base":
        ambient = "0.48 0.47 0.44 1"
        background = "0.58 0.60 0.62 1"
        fog = ""
    elif variant.key == "medium":
        ambient = "0.44 0.43 0.40 1"
        background = "0.52 0.53 0.54 1"
        fog = ""
    else:
        ambient = "0.42 0.41 0.38 1"
        background = "0.48 0.49 0.50 1"
        fog = ""
    world_name = world_label or variant.key
    world = f"""<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="Ruins-Urban-01_{world_name}">
    <gravity>0 0 -9.81</gravity>
    <scene>
      <ambient>{ambient}</ambient>
      <background>{background}</background>
      <shadows>true</shadows>
{fog}
    </scene>
    <physics name="ode_physics" type="ode">
      <max_step_size>0.004</max_step_size>
      <real_time_factor>1</real_time_factor>
      <real_time_update_rate>250</real_time_update_rate>
    </physics>
    <light name="ceiling_area_light" type="point">
      <pose>-11 0 6.8 0 0 0</pose>
      <diffuse>0.68 0.65 0.58 1</diffuse>
      <specular>0.05 0.05 0.05 1</specular>
      <attenuation><range>38</range><constant>0.7</constant><linear>0.02</linear><quadratic>0.002</quadratic></attenuation>
    </light>
    <light name="damaged_east_light" type="point">
      <pose>12 5 5.8 0 0 0</pose>
      <diffuse>0.42 0.48 0.50 1</diffuse>
      <specular>0.03 0.03 0.03 1</specular>
      <attenuation><range>25</range><constant>0.8</constant><linear>0.04</linear><quadratic>0.004</quadratic></attenuation>
    </light>
    <light name="lower_south_light" type="point">
      <pose>-5 -10 3.0 0 0 0</pose>
      <diffuse>0.38 0.31 0.25 1</diffuse>
      <specular>0.02 0.02 0.02 1</specular>
      <attenuation><range>19</range><constant>0.9</constant><linear>0.05</linear><quadratic>0.006</quadratic></attenuation>
    </light>
    <include>
      <uri>model://{model_name}</uri>
    </include>
  </world>
</sdf>
"""
    write_text_lf(path, world)


def write_launches_and_configs():
    config_dir = OUT / "config"
    launch_dir = OUT / "launch"
    config_dir.mkdir(parents=True, exist_ok=True)
    launch_dir.mkdir(parents=True, exist_ok=True)

    yaml = f"""scene_name: Ruins-Urban-01
units: meters
frame_id: map
origin: centered_xy_floor_z0
dimensions:
  x: 42.0
  y: 32.0
  z: 8.0
bounding_box:
  min_x: -21.0
  max_x: 21.0
  min_y: -16.0
  max_y: 16.0
  min_z: 0.0
  max_z: 8.0
uav:
  collision_diameter_D: {PARAMS["collision_diameter_D"]}
  min_required_radius: {PARAMS["min_required_radius"]}
corridors:
  normal_width: 2.7
  narrow_width: 1.45
  squeeze_width: 1.22
  vertical_connector_width: 2.2
vertical_connectors:
  - name: vertical_connector_a
    center: [-4.0, 7.0]
    z_low: 1.35
    z_high: 4.55
  - name: vertical_connector_b
    center: [16.0, -8.5]
    z_low: 1.35
    z_high: 4.55
  - name: vertical_connector_c
    center: [1.5, 0.8]
    z_low: 1.20
    z_high: 4.55
  - name: vertical_connector_d
    center: [-15.0, -12.0]
    z_low: 1.35
    z_high: 4.55
  - name: vertical_connector_e
    center: [-2.5, -10.0]
    z_low: 1.35
    z_high: 4.55
  - name: vertical_connector_f
    center: [6.0, -7.5]
    z_low: 1.35
    z_high: 4.55
variants:
"""
    for v in VARIANTS:
        yaml += f"""  {v.key}:
    seed: {v.seed}
    pcd: ../maps/pcd/Ruins-Urban-01_{v.key}.pcd
    gazebo_world: ../gazebo/worlds/Ruins-Urban-01_{v.key}.world
    mesh_obj: ../meshes/obj/Ruins-Urban-01_{v.key}.obj
    mesh_dae: ../meshes/dae/Ruins-Urban-01_{v.key}.dae
    rubble_count: {v.rubble_count}
    column_count: {v.column_count}
    collapsed_wall_count: {v.collapsed_wall_count}
"""
        if v.key == "complex":
            yaml += "    optional_fog_world: ../gazebo/worlds/Ruins-Urban-01_complex_fog.world\n"
    write_text_lf(config_dir / "ruins_urban_01.yaml", yaml)

    fuel_config = """# Copy or symlink the selected PCD into FUEL/RACER map_generator/resource,
# or keep the absolute path in the map_pub args in the launch snippet.
box_min_x: -21.0
box_max_x: 21.0
box_min_y: -16.0
box_max_y: 16.0
box_min_z: 0.0
box_max_z: 8.0
map_resolution: 0.15
sensing_horizon: 8.0
uav_count: 3
"""
    write_text_lf(config_dir / "fuel_racer_ruins_urban_01.yaml", fuel_config)

    marsim_config = """map:
  frame_id: map
  pointcloud: ../maps/pcd/Ruins-Urban-01_challenge.pcd
  resolution_hint: 0.18
  bounding_box: [-21.0, 21.0, -16.0, 16.0, 0.0, 8.0]
lidar:
  use_case: uav_exploration
  max_range: 30.0
  horizontal_fov_deg: 360.0
  vertical_fov_deg: 90.0
swarm:
  uav_count: 3
  initial_poses:
    - [-19.0, -0.8, 1.2, 0.0]
    - [-19.0, 0.0, 1.6, 0.0]
    - [-19.0, 0.8, 2.0, 0.0]
"""
    write_text_lf(config_dir / "marsim_ruins_urban_01.yaml", marsim_config)

    for v in VARIANTS:
        fuel_launch = f"""<launch>
  <arg name="map_file" default="$(find ruins_urban_01)/maps/pcd/Ruins-Urban-01_{v.key}.pcd"/>
  <arg name="box_min_x" default="-21.0"/>
  <arg name="box_min_y" default="-16.0"/>
  <arg name="box_min_z" default="0.0"/>
  <arg name="box_max_x" default="21.0"/>
  <arg name="box_max_y" default="16.0"/>
  <arg name="box_max_z" default="8.0"/>

  <!-- FUEL/RACER map publisher: replace the original office/pillar map_pub line with this. -->
  <node pkg="map_generator" name="map_pub" type="map_pub" output="screen" args="$(arg map_file)"/>
</launch>
"""
        write_text_lf(launch_dir / f"fuel_map_pub_ruins_urban_01_{v.key}.launch", fuel_launch)

    racer_launch = """<launch>
  <arg name="map_file" default="$(env HOME)/catkin_ws/src/RACER/uav_simulator/map_generator/resource/Ruins-Urban-01_challenge.pcd"/>
  <arg name="drone_num" default="3"/>
  <!-- Use this as a replacement snippet inside RACER's swarm_exploration.launch. -->
  <node pkg="map_generator" name="map_pub" type="map_pub" output="screen" args="$(arg map_file)"/>
  <param name="exploration/box_min_x" value="-21.0"/>
  <param name="exploration/box_min_y" value="-16.0"/>
  <param name="exploration/box_min_z" value="0.0"/>
  <param name="exploration/box_max_x" value="21.0"/>
  <param name="exploration/box_max_y" value="16.0"/>
  <param name="exploration/box_max_z" value="8.0"/>
</launch>
"""
    write_text_lf(launch_dir / "racer_ruins_urban_01_snippet.launch", racer_launch)

    marsim_launch = """<launch>
  <arg name="map_file" default="$(find ruins_urban_01)/maps/pcd/Ruins-Urban-01_challenge.pcd"/>
  <arg name="drone_num" default="3"/>
  <!-- MARSIM variants differ by fork. Keep this as a wiring template:
       load the PCD map into the simulator's pointcloud map parameter, then publish
       quadrotor command topics from Prometheus/PX4 or your planner. -->
  <param name="/marsim/map_file" value="$(arg map_file)"/>
  <param name="/marsim/drone_num" value="$(arg drone_num)"/>
</launch>
"""
    write_text_lf(launch_dir / "marsim_ruins_urban_01_template.launch", marsim_launch)

    gazebo_launch = """<launch>
  <arg name="variant" default="challenge"/>
  <arg name="gui" default="true"/>
  <arg name="paused" default="false"/>
  <arg name="verbose" default="false"/>
  <arg name="world" default="$(find ruins_urban_01)/gazebo/worlds/Ruins-Urban-01_$(arg variant).world"/>
  <include file="$(find gazebo_ros)/launch/empty_world.launch">
    <arg name="world_name" value="$(arg world)"/>
    <arg name="paused" value="$(arg paused)"/>
    <arg name="use_sim_time" value="true"/>
    <arg name="gui" value="$(arg gui)"/>
    <arg name="verbose" value="$(arg verbose)"/>
  </include>
</launch>
"""
    write_text_lf(launch_dir / "gazebo_ruins_urban_01.launch", gazebo_launch)


def write_blender_script(path: Path):
    script = r'''# Blender Python source model for Ruins-Urban-01.
# Run inside Blender:
#   blender --background --python generate_ruins_urban_01_blender.py
#
# This script imports the generated scene JSON and creates editable named boxes.
# It can export OBJ/DAE and save a .blend source file when Blender is available.

import json
import math
import os
from pathlib import Path

import bpy

BASE = Path(__file__).resolve().parents[1]
SCENE_JSON = BASE / "config" / "scene_geometry.json"

with SCENE_JSON.open("r", encoding="utf-8") as f:
    data = json.load(f)

VARIANT = os.environ.get("RUINS_VARIANT", "challenge")
if VARIANT not in data["geometry"]:
    raise ValueError(f"Unknown RUINS_VARIANT={VARIANT!r}; choose one of {sorted(data['geometry'])}")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

materials = {}
palette = {
    "concrete": (0.58, 0.56, 0.52, 1.0),
    "concrete_light": (0.68, 0.66, 0.61, 1.0),
    "dark_concrete": (0.35, 0.35, 0.34, 1.0),
    "rebar": (0.12, 0.12, 0.12, 1.0),
    "rubble": (0.46, 0.42, 0.36, 1.0),
    "brick": (0.43, 0.29, 0.23, 1.0),
    "soil": (0.29, 0.25, 0.20, 1.0),
    "rust": (0.37, 0.20, 0.13, 1.0),
    "hazard": (0.65, 0.18, 0.12, 1.0),
}
for name, color in palette.items():
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    materials[name] = mat

for box in data["geometry"][VARIANT]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=box["center"])
    obj = bpy.context.object
    obj.name = box["name"]
    obj.dimensions = box["size"]
    obj.rotation_euler = box["rpy"]
    obj.data.materials.append(materials.get(box["material"], materials["concrete"]))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Add lights/camera only for inspection. They are not used by PCD generation.
bpy.ops.object.light_add(type="AREA", location=(0, 0, 7.5))
light = bpy.context.object
light.name = "inspection_area_light"
light.data.energy = 700
light.data.size = 18

bpy.ops.object.camera_add(location=(0, -43, 22), rotation=(math.radians(62), 0, 0))
bpy.context.scene.camera = bpy.context.object

blend_path = BASE / "blender" / f"Ruins-Urban-01_{VARIANT}_source.blend"
blend_path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

bpy.ops.wm.obj_export(filepath=str(BASE / "meshes" / "obj" / f"Ruins-Urban-01_{VARIANT}.obj"))
try:
    bpy.ops.wm.collada_export(filepath=str(BASE / "meshes" / "dae" / f"Ruins-Urban-01_{VARIANT}.dae"))
except Exception:
    pass
'''
    write_text_lf(path, script)


def write_random_generator_script(path: Path):
    script = r'''#!/usr/bin/env python3
"""Generate a reproducible randomized Ruins-Urban-01 instance."""

import argparse
import json
import re
import secrets
from dataclasses import asdict
from pathlib import Path

from generate_ruins_package import (
    VARIANTS,
    Variant,
    make_scene,
    validate_navigation,
    write_dae,
    write_model_files,
    write_mtl,
    write_obj,
    write_pcd,
    write_text_lf,
    write_world,
)


BASE = Path(__file__).resolve().parents[1]
PROFILES = {variant.key: variant for variant in VARIANTS}


def safe_asset_key(value):
    key = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if not key:
        raise ValueError("The generated scene name is empty after sanitization.")
    return key


def main():
    parser = argparse.ArgumentParser(
        description="Create a randomized but reproducible Gazebo/PCD ruins instance."
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="challenge")
    parser.add_argument("--seed", type=int, help="Fixed seed. Omit it to get a new random seed.")
    parser.add_argument("--name", help="Optional generated asset suffix.")
    parser.add_argument("--clutter-scale", type=float, default=1.0)
    parser.add_argument("--rubble", type=int)
    parser.add_argument("--columns", type=int)
    parser.add_argument("--collapsed-walls", type=int)
    parser.add_argument("--pcd-step", type=float)
    parser.add_argument("--fog", action="store_true", help="Enable the optional visual fog stressor.")
    args = parser.parse_args()

    if args.clutter_scale <= 0:
        parser.error("--clutter-scale must be greater than zero")

    template = PROFILES[args.profile]
    seed = args.seed if args.seed is not None else secrets.randbelow(2_000_000_000) + 1
    rubble = args.rubble if args.rubble is not None else round(template.rubble_count * args.clutter_scale)
    columns = args.columns if args.columns is not None else round(template.column_count * args.clutter_scale)
    collapsed = (
        args.collapsed_walls
        if args.collapsed_walls is not None
        else round(template.collapsed_wall_count * args.clutter_scale)
    )
    if min(rubble, columns, collapsed) < 0:
        parser.error("Obstacle counts cannot be negative")

    variant = Variant(
        key=args.profile,
        title=f"Randomized {template.title}",
        seed=seed,
        rubble_count=rubble,
        column_count=columns,
        collapsed_wall_count=collapsed,
        pcd_step=args.pcd_step or template.pcd_step,
        second_level_extra=template.second_level_extra,
    )
    asset_key = safe_asset_key(args.name or f"random_{args.profile}_{seed}")
    boxes = make_scene(variant)
    validation = validate_navigation(boxes, variant)
    if not validation["passed"]:
        raise RuntimeError(
            f"Generated seed {seed} failed clearance validation: {validation['blocking_edges']}"
        )

    pcd_path = BASE / "maps" / "pcd" / f"Ruins-Urban-01_{asset_key}.pcd"
    obj_path = BASE / "meshes" / "obj" / f"Ruins-Urban-01_{asset_key}.obj"
    dae_path = BASE / "meshes" / "dae" / f"Ruins-Urban-01_{asset_key}.dae"
    model_dir = BASE / "gazebo" / "models" / f"ruins_urban_01_{asset_key}"
    world_path = BASE / "gazebo" / "worlds" / f"Ruins-Urban-01_{asset_key}.world"
    validation_path = BASE / "validation" / "generated" / f"Ruins-Urban-01_{asset_key}.json"

    for target in (
        pcd_path.parent,
        obj_path.parent,
        dae_path.parent,
        model_dir,
        world_path.parent,
        validation_path.parent,
    ):
        target.mkdir(parents=True, exist_ok=True)

    write_mtl(BASE / "meshes" / "obj" / "ruins_urban_01.mtl")
    pcd_points = write_pcd(pcd_path, boxes, variant.pcd_step)
    write_obj(obj_path, boxes, "ruins_urban_01.mtl")
    write_dae(dae_path, boxes)
    write_model_files(model_dir, variant, boxes, asset_key=asset_key)
    (model_dir / "meshes").mkdir(exist_ok=True)
    (model_dir / "meshes" / dae_path.name).write_bytes(dae_path.read_bytes())
    write_world(
        world_path,
        variant,
        fog_enabled=args.fog,
        world_label=asset_key,
        model_key=asset_key,
    )

    manifest = {
        "asset_key": asset_key,
        "profile": args.profile,
        "seed": seed,
        "fog_enabled": args.fog,
        "parameters": asdict(variant),
        "box_count": len(boxes),
        "pcd_points": pcd_points,
        "pcd": str(pcd_path),
        "world": str(world_path),
        "model": str(model_dir),
        "validation": validation,
    }
    write_text_lf(validation_path, json.dumps(manifest, indent=2))

    print("Generated randomized ruins instance.")
    print(f"asset_key: {asset_key}")
    print(f"seed: {seed}")
    print(f"world: {world_path}")
    print(f"pcd: {pcd_path}")
    print("")
    print("Launch with:")
    print("  source ~/catkin_ws/devel/setup.bash")
    print('  source "$(rospack find ruins_urban_01)/setup_env.sh"')
    print(f"  roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:={asset_key}")


if __name__ == "__main__":
    main()
'''
    write_text_lf(path, script)


def write_ros_package_files():
    package_xml = """<?xml version="1.0"?>
<package format="2">
  <name>ruins_urban_01</name>
  <version>0.6.0</version>
  <description>Ruins-Urban-01 3D rubble environment assets for UAV exploration simulation.</description>
  <maintainer email="zhanghang1122@users.noreply.github.com">zhanghang1122</maintainer>
  <license>MIT</license>

  <buildtool_depend>catkin</buildtool_depend>
  <exec_depend>roslaunch</exec_depend>
  <exec_depend>gazebo_ros</exec_depend>

  <export>
    <gazebo_ros gazebo_model_path="${prefix}/gazebo/models"/>
  </export>
</package>
"""
    cmake = """cmake_minimum_required(VERSION 3.0.2)
project(ruins_urban_01)

find_package(catkin REQUIRED)

catkin_package()

install(DIRECTORY
  blender
  config
  docs
  experiments
  gazebo
  launch
  maps
  meshes
  scripts
  validation
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
"""
    setup = """#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GAZEBO_MODEL_PATH="${SCRIPT_DIR}/gazebo/models${GAZEBO_MODEL_PATH:+:${GAZEBO_MODEL_PATH}}"

echo "Ruins-Urban-01 is ready."
echo "Gazebo model path added: ${SCRIPT_DIR}/gazebo/models"
echo "Example:"
echo "  roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:=challenge"
"""
    write_text_lf(OUT / "package.xml", package_xml)
    write_text_lf(OUT / "CMakeLists.txt", cmake)
    write_text_lf(OUT / "setup_env.sh", setup)


def point_oriented_box_distance(p, box: Box) -> float:
    # Transform point into local box coordinates and compute Euclidean distance outside box.
    r = rot_matrix(box.rpy)
    # transpose rotation for inverse
    d = sub(p, box.center)
    local = (
        r[0][0] * d[0] + r[1][0] * d[1] + r[2][0] * d[2],
        r[0][1] * d[0] + r[1][1] * d[1] + r[2][1] * d[2],
        r[0][2] * d[0] + r[1][2] * d[1] + r[2][2] * d[2],
    )
    hx, hy, hz = box.size[0] / 2, box.size[1] / 2, box.size[2] / 2
    dx = max(abs(local[0]) - hx, 0.0)
    dy = max(abs(local[1]) - hy, 0.0)
    dz = max(abs(local[2]) - hz, 0.0)
    if dx == dy == dz == 0.0:
        return -min(hx - abs(local[0]), hy - abs(local[1]), hz - abs(local[2]))
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def graph_metrics(nodes, edges) -> dict:
    degree = {name: 0 for name in nodes}
    total_length = 0.0
    vertical_edges = 0
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
        total_length += math.dist(nodes[a], nodes[b])
        if abs(nodes[a][2] - nodes[b][2]) > 0.8:
            vertical_edges += 1
    dead_ends = [name for name, value in degree.items() if value == 1 and name != "entry"]
    branch_nodes = [name for name, value in degree.items() if value >= 3]
    loops = max(0, len(edges) - len(nodes) + 1)
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "branch_node_count": len(branch_nodes),
        "branch_nodes": branch_nodes,
        "independent_loop_count": loops,
        "dead_end_count": len(dead_ends),
        "dead_ends": dead_ends,
        "vertical_connector_count": vertical_edges,
        "reference_graph_length_m": round(total_length, 2),
    }


def validate_navigation(boxes: list[Box], variant: Variant) -> dict:
    nodes, edges = navigation_graph(variant)
    checked_edges = []
    min_clearance = 999.0
    blocking = []
    relevant = [b for b in boxes if b.role not in {"floor", "connector_marker"}]
    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        length = math.dist(pa, pb)
        samples = max(5, int(math.ceil(length / 0.25)))
        edge_min = 999.0
        edge_nearest = ""
        for i in range(samples + 1):
            t = i / samples
            p = (
                pa[0] * (1 - t) + pb[0] * t,
                pa[1] * (1 - t) + pb[1] * t,
                pa[2] * (1 - t) + pb[2] * t,
            )
            nearest_box, clearance = min(
                ((box, point_oriented_box_distance(p, box)) for box in relevant),
                key=lambda item: item[1],
            )
            if clearance < edge_min:
                edge_min = clearance
                edge_nearest = nearest_box.name
        min_clearance = min(min_clearance, edge_min)
        checked_edges.append(
            {"edge": [a, b], "min_clearance_m": round(edge_min, 3), "nearest_obstacle": edge_nearest}
        )
        if edge_min < PARAMS["min_required_radius"]:
            blocking.append(
                {"edge": [a, b], "min_clearance_m": round(edge_min, 3), "nearest_obstacle": edge_nearest}
            )
    return {
        "required_radius_m": PARAMS["min_required_radius"],
        "min_centerline_clearance_m": round(min_clearance, 3),
        "topology": graph_metrics(nodes, edges),
        "checked_edges": checked_edges,
        "blocking_edges": blocking,
        "passed": not blocking,
    }


def write_readme(summary):
    readme = f"""# Ruins-Urban-01

Ruins-Urban-01 is a reproducible, thesis-oriented 3D rubble environment for multi-UAV exploration on Ubuntu 20.04 / ROS Noetic / PX4 / Prometheus workflows.

This folder is a ROS package named `ruins_urban_01` inside the parent paper repository. Clone the parent repository under `~/catkin_ws/src`, then build or source the workspace so `$(find ruins_urban_01)` works in launch files.

The source representation is the Blender Python script in `scripts/generate_ruins_urban_01_blender.py`. The generated runtime assets are:

- `maps/pcd/*.pcd`: primary maps for MARSIM, FUEL, RACER, and point-cloud based planners.
- `meshes/obj/*.obj` and `meshes/dae/*.dae`: platform-neutral mesh exports.
- `gazebo/models/*` and `gazebo/worlds/*.world`: Gazebo Classic usable model/world files.
- `config/*.yaml`: scene dimensions, seeds, bounds, and integration hints.
- `launch/*.launch`: example ROS launch snippets/templates.

## Scene Design

- Size: 42 m x 32 m x 8 m.
- UAV collision diameter parameter: `D = 0.65 m`.
- Normal corridor width: 2.7 m.
- Narrow corridor width: 1.45 m.
- Squeeze passage width: 1.22 m (challenge variant only).
- Vertical connector width: 2.2 m.
- Features: irregular corridors, occluded forks, loops, dead ends, broken facades, tilted slabs, rubble clusters, repeated columns, low-feature passages, overhead debris, partial second level, and six vertical connectors.

The paper main `challenge` scene contains {summary['challenge']['validation']['topology']['node_count']} reference topology nodes,
{summary['challenge']['validation']['topology']['edge_count']} traversable connections,
{summary['challenge']['validation']['topology']['branch_node_count']} branch nodes,
{summary['challenge']['validation']['topology']['independent_loop_count']} independent loops,
{summary['challenge']['validation']['topology']['dead_end_count']} dead ends, and
{summary['challenge']['validation']['topology']['vertical_connector_count']} vertical connectors.
These reference paths exist only for generation-time validation and are not exposed as task partitions to the UAVs.

The scene is not pre-partitioned for UAV assignment. Any naming of rooms, forks, or sections exists only for modeling and debugging. Exploration algorithms should discover frontiers online from local sensing.

## Variants

| Variant | Seed | PCD points | Purpose |
|---|---:|---:|---|
| base | 240701 | {summary['base']['pcd_points']} | Basic validation and single-UAV bring-up |
| medium | 240702 | {summary['medium']['pcd_points']} | Three-UAV debugging with denser rubble |
| complex | 240703 | {summary['complex']['pcd_points']} | Complexity pilot only; not final paper data |
| challenge | 240704 | {summary['challenge']['pcd_points']} | Frozen paper main scene |

## Recommended Use

Update the parent Git repository inside the Ubuntu VM, then rebuild the catkin workspace:

```bash
cd ~/catkin_ws/src/multi-uav-cooperative-exploration
git fetch origin
git switch verified-runtime
git pull --ff-only
cd ~/catkin_ws
catkin_make -j2
source /opt/ros/noetic/setup.bash
source devel/setup.bash
```

For FUEL/RACER, copy or symlink a selected PCD into the package's `map_generator/resource` directory, then replace the original `map_pub` PCD argument and set the exploration bounding box:

```bash
roslaunch exploration_manager rviz.launch
roslaunch exploration_manager swarm_exploration.launch
```

Use these bounds:

```text
box_min_x = -21.0
box_max_x =  21.0
box_min_y = -16.0
box_max_y =  16.0
box_min_z =   0.0
box_max_z =   8.0
```

For Gazebo Classic/PX4, add `gazebo/models` to `GAZEBO_MODEL_PATH`, then open one of the world files:

```bash
source ~/catkin_ws/devel/setup.bash
source "$(rospack find ruins_urban_01)/setup_env.sh"
roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:=challenge
```

## Randomized Procedural Instances

Keep `base`, `medium`, `complex`, and `challenge` unchanged as fair, reproducible benchmark maps. Generate additional
random instances for generalization and stress tests:

```bash
cd "$(rospack find ruins_urban_01)"
python3 scripts/generate_random_ruins.py --profile challenge
```

The command prints the generated seed, world, PCD, and launch command. Omitting `--seed` creates a new
instance every time. To reproduce an exact instance or control clutter:

```bash
python3 scripts/generate_random_ruins.py \
  --profile challenge \
  --seed 20260724 \
  --clutter-scale 1.20
```

Individual counts can also be controlled with `--rubble`, `--columns`, and `--collapsed-walls`.
Do not use `--fog` in the main geometry comparison; reserve it for a separate perception stress test.
Every generated instance writes a manifest under `validation/generated/` so failed runs remain reproducible.

For Prometheus, use the Gazebo world as the environment and keep UAV spawning near the entrance:

```text
UAV1: x=-19.0, y=-0.8, z=1.2
UAV2: x=-19.0, y= 0.0, z=1.6
UAV3: x=-19.0, y= 0.8, z=2.0
```

## Validation

Generation ran a basic centerline clearance check on the intended navigation graph. This does not prove a planner will succeed, but it catches accidental sealed corridors.

| Variant | Passed | Minimum clearance |
|---|---:|---:|
| base | {summary['base']['validation']['passed']} | {summary['base']['validation']['min_centerline_clearance_m']} m |
| medium | {summary['medium']['validation']['passed']} | {summary['medium']['validation']['min_centerline_clearance_m']} m |
| complex | {summary['complex']['validation']['passed']} | {summary['complex']['validation']['min_centerline_clearance_m']} m |
| challenge | {summary['challenge']['validation']['passed']} | {summary['challenge']['validation']['min_centerline_clearance_m']} m |

## Notes

- Start development on `base`, move to `medium`, use `complex` only for a complexity pilot, and reserve `challenge` for paper experiments.
- Use randomized starts, randomized obstacle seeds, and repeated trials later to prove autonomy rather than rehearsed trajectories.
- The included topology-related names are debug names only; do not use them as ground-truth task partitions in the algorithm.
- See `docs/design_basis.md` for the literature-informed design rationale and the limits of the benchmark.
- The default worlds are clear so geometry and planning difficulty can be evaluated independently. Use
  `variant:=complex_fog` only for a separate perception-degradation stress test.
"""
    write_text_lf(OUT / "README.md", readme)


def write_design_basis(summary):
    challenge_topology = summary["challenge"]["validation"]["topology"]
    text = f"""# Ruins-Urban-01 v3: Literature-Informed Design Basis

This scene is a compact, reproducible UAV benchmark inspired by recurring challenges reported in
subterranean and multi-UAV exploration research. It is not a geometric copy of a DARPA course and
does not claim that obstacle count alone measures environmental complexity.

## Evidence Used

1. DARPA Subterranean Challenge program overview:
   https://www.darpa.mil/research/programs/darpa-subterranean-challenge
   The official description identifies autonomous mapping and navigation in human-made urban underground
   structures, tunnels, and caves under degraded perception and difficult terrain as the target problem.
2. Zhou B, Pan J, Gao F, Shen S. FUEL: Fast UAV Exploration Using Incremental Frontier Structure and
   Hierarchical Planning. IEEE Robotics and Automation Letters, 2021.
   https://doi.org/10.1109/LRA.2021.3051563
   Supports frontier-driven autonomous exploration as the single-UAV baseline and uses bounded 3D map space.
3. Ribeiro M, Basiri M. Efficient 3D Exploration with Distributed Multi-UAV Teams: Integrating Frontier-Based
   and Next-Best-View Planning. Drones, 2024, 8(11):630.
   https://doi.org/10.3390/drones8110630
   Supports evaluating distributed multi-UAV 3D exploration with completion time, explored volume, and overlap.
4. Wen C, Dong W, Xie W, Cai M, Liu R. Distributed cooperative area search method for UAV swarms based on
   revisit mechanism. Acta Aeronautica et Astronautica Sinica, 2023, 44(11):327561.
   https://doi.org/10.7527/S1000-6893.2022.27561
   Supports online information updates and repeated-run statistical comparison rather than one scripted trajectory.
5. GA-HP: A game-assisted hierarchical planner for multi-UAV coverage in unknown environments.
   Aerospace Science and Technology, 2025, 166:110624.
   https://doi.org/10.1016/j.ast.2025.110624
   Supports separating centralized task allocation from safe local planning in unknown environments.

## Implemented Complexity Dimensions

| Dimension | Challenge variant |
|---|---:|
| Physical size | 42 x 32 x 8 m |
| Reference topology nodes | {challenge_topology['node_count']} |
| Traversable graph edges | {challenge_topology['edge_count']} |
| Branch nodes | {challenge_topology['branch_node_count']} |
| Independent loops | {challenge_topology['independent_loop_count']} |
| Dead ends | {challenge_topology['dead_end_count']} |
| Vertical connectors | {challenge_topology['vertical_connector_count']} |
| Reference graph length | {challenge_topology['reference_graph_length_m']} m |
| Minimum validated centerline clearance | {summary['challenge']['validation']['min_centerline_clearance_m']} m |
| UAV collision diameter D | {PARAMS['collision_diameter_D']} m |
| Narrow/squeeze widths | 1.45 m / 1.22 m |

Geometric complexity comes from connected structure, not random clutter alone. The challenge scene combines
an irregular main spine, multi-branch ground loops, seven dead ends, a true upper network, six altitude
transitions, breached wall shells, tilted facade fragments, fallen slabs, rubble clusters, overhead beams,
repetitive columns, and occluded junctions. Rubble is generated with fixed seeds and constrained so it cannot
accidentally seal the validated reference routes.

## Intended Experimental Use

- `base`: integration and single-UAV bring-up.
- `medium`: multi-UAV debugging with two vertical connectors and five loops.
- `complex`: complexity pilot; do not report it as the final paper main environment.
- `challenge`: frozen main environment for B1/B2/B3/proposed-method comparisons.

Run at least 20 repeated trials per method with varied start yaw, sensor noise, communication loss, and
additional obstacle seeds. Report coverage-time curves, success rate, total fleet path length, repeated
coverage, minimum inter-UAV distance, map completeness, and runtime. A single successful video is not
evidence of autonomy.

The navigation graph stored in validation files is a generator oracle used only to ensure that the world
is physically traversable. Exploration code must not read it.
"""
    docs_dir = OUT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    write_text_lf(docs_dir / "design_basis.md", text)


def write_preview_svg(path: Path, variant: Variant, boxes: list[Box]):
    nodes, edges = navigation_graph(variant)
    colors = {
        "concrete": "#87857f",
        "concrete_light": "#aaa79f",
        "dark_concrete": "#414345",
        "rebar": "#242526",
        "rubble": "#6f6253",
        "brick": "#70493b",
        "soil": "#4a4035",
        "rust": "#63382b",
        "hazard": "#a12f25",
    }
    scale = 12.0
    panel_w, panel_h = 42 * scale, 32 * scale
    left_x, top_y = 55.0, 78.0
    right_x = 665.0

    def xy(panel_x, x, y):
        return panel_x + (x + 21.0) * scale, top_y + (16.0 - y) * scale

    def rect_svg(panel_x, box: Box, opacity: float):
        cx, cy = xy(panel_x, box.center[0], box.center[1])
        w, h = box.size[0] * scale, box.size[1] * scale
        angle = -math.degrees(box.rpy[2])
        fill = colors.get(box.material, "#888888")
        return (
            f'<rect x="{cx - w / 2:.2f}" y="{cy - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" stroke="#18191a" stroke-width="0.45" '
            f'transform="rotate({angle:.2f} {cx:.2f} {cy:.2f})"/>'
        )

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="520" viewBox="0 0 1240 520">',
        '<rect width="1240" height="520" fill="#1f2225"/>',
        f'<text x="55" y="34" fill="#f1f2f3" font-family="sans-serif" font-size="22">Ruins-Urban-01 {variant.key} validation preview</text>',
        '<text x="55" y="58" fill="#aeb4ba" font-family="sans-serif" font-size="13">Reference graph overlay is for generation QA only; it is not available to exploration algorithms.</text>',
        f'<rect x="{left_x}" y="{top_y}" width="{panel_w}" height="{panel_h}" fill="#303438" stroke="#70777d"/>',
        f'<rect x="{right_x}" y="{top_y}" width="{panel_w}" height="{panel_h}" fill="#303438" stroke="#70777d"/>',
        f'<text x="{left_x}" y="{top_y - 10}" fill="#d8dcdf" font-family="sans-serif" font-size="15">Ground / low level</text>',
        f'<text x="{right_x}" y="{top_y - 10}" fill="#d8dcdf" font-family="sans-serif" font-size="15">Upper / overhead structure</text>',
    ]
    for box in boxes:
        if box.role == "floor":
            continue
        bottom = box.center[2] - box.size[2] / 2
        top = box.center[2] + box.size[2] / 2
        if bottom < 2.4:
            svg.append(rect_svg(left_x, box, 0.88))
        if top > 3.15:
            svg.append(rect_svg(right_x, box, 0.78))

    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        panel = right_x if pa[2] > 3.5 and pb[2] > 3.5 else left_x
        ax, ay = xy(panel, pa[0], pa[1])
        bx, by = xy(panel, pb[0], pb[1])
        color = "#f4c95d" if panel == right_x else "#51d0d8"
        svg.append(
            f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
            f'stroke="{color}" stroke-width="1.6" stroke-dasharray="5 4" opacity="0.9"/>'
        )
    svg.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, "\n".join(svg))


def write_portable_zip():
    zip_path = OUT.parent / "ruins_urban_01.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file_path in sorted(p for p in OUT.rglob("*") if p.is_file()):
            relative = file_path.relative_to(OUT.parent).as_posix()
            info = zipfile.ZipInfo(relative)
            info.create_system = 3
            mode = 0o755 if file_path.name == "setup_env.sh" or file_path.suffix == ".py" else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file_path.read_bytes())


def main():
    for rel in [
        "maps/pcd",
        "meshes/obj",
        "meshes/dae",
        "gazebo/models",
        "gazebo/worlds",
        "launch",
        "config",
        "scripts",
        "validation",
        "validation/previews",
        "docs",
        "blender",
    ]:
        (OUT / rel).mkdir(parents=True, exist_ok=True)

    write_mtl(OUT / "meshes" / "obj" / "ruins_urban_01.mtl")
    summary = {}
    scene_json = {"params": PARAMS, "variants": [v.key for v in VARIANTS], "geometry": {}}
    for variant in VARIANTS:
        boxes = make_scene(variant)
        scene_json["geometry"][variant.key] = [asdict(b) for b in boxes]
        pcd_points = write_pcd(OUT / "maps" / "pcd" / f"Ruins-Urban-01_{variant.key}.pcd", boxes, variant.pcd_step)
        write_obj(OUT / "meshes" / "obj" / f"Ruins-Urban-01_{variant.key}.obj", boxes, "ruins_urban_01.mtl")
        dae_path = OUT / "meshes" / "dae" / f"Ruins-Urban-01_{variant.key}.dae"
        write_dae(dae_path, boxes)
        model_dir = OUT / "gazebo" / "models" / f"ruins_urban_01_{variant.key}"
        write_model_files(model_dir, variant, boxes)
        write_text_lf(model_dir / "meshes" / dae_path.name, dae_path.read_text(encoding="ascii"))
        write_world(OUT / "gazebo" / "worlds" / f"Ruins-Urban-01_{variant.key}.world", variant)
        if variant.key == "complex":
            write_world(
                OUT / "gazebo" / "worlds" / "Ruins-Urban-01_complex_fog.world",
                variant,
                fog_enabled=True,
                world_label="complex_fog",
            )
        validation = validate_navigation(boxes, variant)
        write_text_lf(
            OUT / "validation" / f"Ruins-Urban-01_{variant.key}_validation.json",
            json.dumps(validation, indent=2),
        )
        write_preview_svg(
            OUT / "validation" / "previews" / f"Ruins-Urban-01_{variant.key}_preview.svg",
            variant,
            boxes,
        )
        summary[variant.key] = {
            "box_count": len(boxes),
            "pcd_points": pcd_points,
            "validation": validation,
        }

    write_text_lf(OUT / "config" / "scene_geometry.json", json.dumps(scene_json, indent=2))
    write_launches_and_configs()
    write_blender_script(OUT / "scripts" / "generate_ruins_urban_01_blender.py")
    write_random_generator_script(OUT / "scripts" / "generate_random_ruins.py")
    write_ros_package_files()
    write_readme(summary)
    write_design_basis(summary)
    write_text_lf(
        OUT / "config" / "complexity_metrics.json",
        json.dumps({key: value["validation"]["topology"] for key, value in summary.items()}, indent=2),
    )
    write_text_lf(OUT / "validation" / "generation_summary.json", json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
