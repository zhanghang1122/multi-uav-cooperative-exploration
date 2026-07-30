#!/usr/bin/env python3
"""Generate the literature-grounded Building-Interior benchmark family.

This generator deliberately does not encode frontiers, routes, room labels or
task partitions.  It exports only geometry and *offline* truth assets.  The
online explorer receives a bounded workspace and an initially unknown map.

The three fixed scenes follow the controlled-complexity protocol used by
recent aerial-exploration literature: a structured office, a cluttered damaged
building interior, and a topology/occlusion stress scene.  Randomized layouts
are intentionally not generated here; they are a later generalization test and
must never replace the fixed comparison scenes.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from generate_ruins_package import Box, write_dae, write_mtl, write_obj, write_pcd


ROOT = Path(__file__).resolve().parents[1]
PCD_STEP_M = 0.20
WALL_THICKNESS_M = 0.28
DOOR_WIDTH_M = 2.20


@dataclass(frozen=True)
class SceneSpec:
    key: str
    title: str
    dimensions_m: tuple[float, float, float]
    entry_pose_m: tuple[float, float, float]
    corridor_normal_d: float
    corridor_narrow_d: float
    loops: int
    dead_ends: int
    room_count: int
    objective: str


SCENES = (
    SceneSpec(
        "s1_structured_office",
        "Building-Interior-S1 Structured Office",
        (18.0, 30.0, 3.0),
        (-7.1, 0.0, 1.4),
        4.0,
        3.0,
        1,
        2,
        6,
        "Single-UAV functional and baseline comparison scene.",
    ),
    SceneSpec(
        "s2_damaged_building",
        "Building-Interior-S2 Damaged Building",
        (30.0, 30.0, 3.5),
        (-13.0, 0.0, 1.5),
        4.0,
        2.7,
        2,
        5,
        10,
        "Paper main scene: occlusion, loops, dead ends and three-way frontier competition.",
    ),
    SceneSpec(
        "s3_topology_stress",
        "Building-Interior-S3 Topology Stress",
        (36.0, 36.0, 3.5),
        (-16.0, 0.0, 1.5),
        4.0,
        2.6,
        4,
        8,
        14,
        "Large connected stress scene for three-UAV coordination and generalization.",
    ),
)


MATERIAL_COLORS = {
    "floor": (0.17, 0.20, 0.22),
    "wall": (0.66, 0.69, 0.70),
    "partition": (0.50, 0.55, 0.58),
    "column": (0.40, 0.46, 0.50),
    "equipment": (0.30, 0.43, 0.53),
    "debris": (0.58, 0.37, 0.24),
    "ceiling": (0.76, 0.78, 0.78),
}


def write_text_lf(path: Path, text: str):
    """Write text on Python 3.8+ with stable LF newlines."""
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(text)


def add_box(boxes: list[Box], name: str, center, size, material: str, role: str, rpy=(0.0, 0.0, 0.0)):
    boxes.append(Box(name, tuple(center), tuple(size), tuple(rpy), material, role))


def add_wall(boxes: list[Box], name: str, p0: tuple[float, float], p1: tuple[float, float], height: float, material="wall"):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        return
    add_box(
        boxes,
        name,
        ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, height / 2),
        (length, WALL_THICKNESS_M, height),
        material,
        "wall",
        (0.0, 0.0, math.atan2(dy, dx)),
    )


def add_wall_with_openings(
    boxes: list[Box],
    name: str,
    p0: tuple[float, float],
    p1: tuple[float, float],
    openings: Iterable[tuple[float, float]],
    height: float,
    material="wall",
):
    """Add a straight wall, leaving intervals open for doors/passages.

    Openings are expressed as (centre distance along wall, width).  They are
    geometric building openings, not exploration goals.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        return
    ux, uy = dx / length, dy / length
    intervals = []
    for centre, width in openings:
        left = max(0.0, centre - width / 2)
        right = min(length, centre + width / 2)
        if right > left:
            intervals.append((left, right))
    intervals.sort()
    merged: list[tuple[float, float]] = []
    for left, right in intervals:
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    cursor = 0.0
    section = 0
    for left, right in merged + [(length, length)]:
        if left - cursor > 0.08:
            a = (p0[0] + ux * cursor, p0[1] + uy * cursor)
            b = (p0[0] + ux * left, p0[1] + uy * left)
            add_wall(boxes, f"{name}_{section:02d}", a, b, height, material)
            section += 1
        cursor = right


def add_envelope(boxes: list[Box], scene: SceneSpec):
    x, y, z = scene.dimensions_m
    hx, hy = x / 2, y / 2
    add_box(boxes, "floor", (0.0, 0.0, -0.10), (x, y, 0.20), "floor", "floor")
    add_wall(boxes, "envelope_north", (-hx, hy), (hx, hy), z, "wall")
    add_wall(boxes, "envelope_south", (-hx, -hy), (hx, -hy), z, "wall")
    add_wall(boxes, "envelope_east", (hx, -hy), (hx, hy), z, "wall")
    # The 3.4 m west opening is the only physical entrance.  It is not a
    # preplanned direction: the drone begins immediately inside this opening.
    add_wall_with_openings(boxes, "envelope_west", (-hx, -hy), (-hx, hy), [(hy, 3.4)], z, "wall")


def add_room_clutter(boxes: list[Box], prefix: str, items: list[tuple[float, float, float, float, float, str]]):
    for index, (x, y, sx, sy, sz, material) in enumerate(items):
        add_box(boxes, f"{prefix}_{index:02d}", (x, y, sz / 2), (sx, sy, sz), material, "obstacle")


def build_s1(scene: SceneSpec) -> list[Box]:
    boxes: list[Box] = []
    add_envelope(boxes, scene)
    h = scene.dimensions_m[2]
    # Four circulation corridors and six rooms.  Walls stop at explicit door
    # openings; there are no decorative floating panels.
    add_wall_with_openings(boxes, "s1_north_divider", (-9, 5), (9, 5), [(3.0, DOOR_WIDTH_M), (12.5, DOOR_WIDTH_M)], h, "partition")
    add_wall_with_openings(boxes, "s1_south_divider", (-9, -5), (9, -5), [(5.0, DOOR_WIDTH_M), (14.0, DOOR_WIDTH_M)], h, "partition")
    add_wall_with_openings(boxes, "s1_west_divider", (-3, -15), (-3, 15), [(4.5, DOOR_WIDTH_M), (14.0, DOOR_WIDTH_M), (24.0, DOOR_WIDTH_M)], h, "partition")
    add_wall_with_openings(boxes, "s1_east_divider", (3, -15), (3, 15), [(7.0, DOOR_WIDTH_M), (17.0, DOOR_WIDTH_M), (25.0, DOOR_WIDTH_M)], h, "partition")
    add_room_clutter(boxes, "s1_equipment", [
        (-6.2, 9.5, 2.2, 0.7, 1.4, "equipment"), (-6.2, -9.0, 2.0, 0.7, 1.4, "equipment"),
        (6.3, 10.2, 2.4, 0.7, 1.4, "equipment"), (6.0, -9.4, 2.2, 0.7, 1.4, "equipment"),
        (-1.0, 10.5, 1.5, 1.1, 0.9, "equipment"), (0.8, -10.5, 1.4, 1.2, 0.9, "equipment"),
    ])
    for idx, (x, y) in enumerate(((-1.2, 1.6), (1.2, 1.6), (-1.2, -1.6), (1.2, -1.6))):
        add_box(boxes, f"s1_column_{idx:02d}", (x, y, h / 2), (0.52, 0.52, h), "column", "column")
    return boxes


def build_s2(scene: SceneSpec) -> list[Box]:
    boxes: list[Box] = []
    add_envelope(boxes, scene)
    h = scene.dimensions_m[2]
    # This is a coherent building floor: a central atrium and four wings, not
    # independent labelled regions.  Doors and turns create occluded frontier
    # branches which only become known from online observations.
    add_wall_with_openings(boxes, "s2_north_ring", (-15, 6), (15, 6), [(4.0, 2.8), (15.0, 2.6), (25.0, 2.8)], h, "partition")
    add_wall_with_openings(boxes, "s2_south_ring", (-15, -6), (15, -6), [(5.0, 2.8), (15.0, 2.6), (25.0, 2.8)], h, "partition")
    add_wall_with_openings(boxes, "s2_west_ring", (-6, -15), (-6, 15), [(5.0, 2.8), (15.0, 2.8), (25.0, 2.6)], h, "partition")
    add_wall_with_openings(boxes, "s2_east_ring", (6, -15), (6, 15), [(4.0, 2.6), (15.0, 2.8), (26.0, 2.6)], h, "partition")
    # Secondary room separators yield dead-end rooms and line-of-sight breaks.
    add_wall_with_openings(boxes, "s2_north_west_rooms", (-10.5, 6), (-10.5, 15), [(4.2, DOOR_WIDTH_M)], h, "wall")
    add_wall_with_openings(boxes, "s2_north_east_rooms", (10.5, 6), (10.5, 15), [(5.0, DOOR_WIDTH_M)], h, "wall")
    add_wall_with_openings(boxes, "s2_south_west_rooms", (-10.5, -15), (-10.5, -6), [(4.5, DOOR_WIDTH_M)], h, "wall")
    add_wall_with_openings(boxes, "s2_south_east_rooms", (10.5, -15), (10.5, -6), [(4.0, DOOR_WIDTH_M)], h, "wall")
    # Short collapse walls are bounded inside rooms, never across a corridor.
    for idx, (x, y, sx, sy, yaw) in enumerate((
        (-12.1, 10.6, 2.8, 0.42, 0.25), (-8.2, -11.0, 2.5, 0.42, -0.34),
        # Keep the east-side doorway clear after safety-radius inflation.
        # The remnants are intentionally deep inside the rooms rather than
        # crossing a passage and creating a visually plausible but impossible
        # exploration area.
        (13.0, 13.0, 2.4, 0.42, -0.26), (13.0, -13.0, 2.3, 0.42, 0.31),
    )):
        add_box(boxes, f"s2_partial_collapse_{idx:02d}", (x, y, 1.05), (sx, sy, 2.1), "debris", "collapse", (0.0, 0.0, yaw))
    for idx, (x, y) in enumerate(((-3.6, 3.6), (0.0, 3.6), (3.6, 3.6), (-3.6, -3.6), (0.0, -3.6), (3.6, -3.6))):
        add_box(boxes, f"s2_atrium_column_{idx:02d}", (x, y, h / 2), (0.58, 0.58, h), "column", "column")
    add_room_clutter(boxes, "s2_equipment", [
        (-13.0, 8.5, 2.6, 0.65, 1.8, "equipment"), (-8.0, 8.7, 2.8, 0.65, 1.8, "equipment"),
        (8.0, 8.5, 2.8, 0.65, 1.8, "equipment"), (13.0, 8.7, 2.6, 0.65, 1.8, "equipment"),
        (-13.0, -8.7, 2.8, 0.65, 1.8, "equipment"), (-8.0, -8.5, 2.4, 0.65, 1.8, "equipment"),
        (8.0, -8.6, 2.8, 0.65, 1.8, "equipment"), (13.0, -8.4, 2.5, 0.65, 1.8, "equipment"),
        (-11.5, 2.6, 1.3, 1.2, 1.1, "equipment"), (11.6, -2.8, 1.3, 1.2, 1.1, "equipment"),
    ])
    # Ceiling fragments stay below the roof and above the intended flight band;
    # they are local structural remnants, not unsupported horizontal panels.
    for idx, (x, y, sx, sy) in enumerate(((-12.0, 12.5, 3.0, 1.4), (12.0, -12.5, 3.0, 1.4))):
        add_box(boxes, f"s2_ceiling_remnant_{idx:02d}", (x, y, 3.18), (sx, sy, 0.24), "ceiling", "ceiling")
    return boxes


def build_s3(scene: SceneSpec) -> list[Box]:
    boxes: list[Box] = []
    add_envelope(boxes, scene)
    h = scene.dimensions_m[2]
    # A connected ring-and-branch building topology.  Unlike an empty maze,
    # each wing contains realistic racks, equipment and bounded damage.
    # Door centres are deliberately offset across each grid line.  A regular
    # closed lattice would look complex in a screenshot but would create many
    # disconnected cells, invalidating an autonomous-exploration benchmark.
    openings = [(3.0, 2.4), (5.0, 2.6), (9.0, 2.4), (18.0, 2.8), (27.0, 2.4), (31.0, 2.6), (33.0, 2.4)]
    for y, label in ((-12, "south"), (-6, "south_inner"), (6, "north_inner"), (12, "north")):
        add_wall_with_openings(boxes, f"s3_horizontal_{label}", (-18, y), (18, y), openings, h, "partition")
    for x, label in ((-12, "west"), (-6, "west_inner"), (6, "east_inner"), (12, "east")):
        add_wall_with_openings(boxes, f"s3_vertical_{label}", (x, -18), (x, 18), openings, h, "partition")
    # Offset internal barriers create turn-dependent visibility and dead ends.
    barriers = [
        (-15.0, 9.2, 3.6, 0.34, 0.0), (-9.0, 15.0, 0.34, 3.6, 0.0),
        (9.0, 15.0, 0.34, 3.6, 0.0), (15.0, 9.2, 3.6, 0.34, 0.0),
        (-15.0, -9.2, 3.6, 0.34, 0.0), (-9.0, -15.0, 0.34, 3.6, 0.0),
        (9.0, -15.0, 0.34, 3.6, 0.0), (15.0, -9.2, 3.6, 0.34, 0.0),
    ]
    for idx, (x, y, sx, sy, yaw) in enumerate(barriers):
        add_box(boxes, f"s3_visibility_barrier_{idx:02d}", (x, y, h / 2), (sx, sy, h), "wall", "wall", (0.0, 0.0, yaw))
    # Storage racks: rows are placed inside rooms, leaving all ring corridors
    # and doorways geometrically open.
    racks = []
    for y in (-15.0, -9.0, 9.0, 15.0):
        for x in (-15.0, -9.0, 9.0, 15.0):
            racks.append((x, y, 2.8, 0.72, 2.0, "equipment"))
    racks.extend([(-3.2, 14.7, 1.8, 1.0, 1.2, "equipment"), (3.2, -14.7, 1.8, 1.0, 1.2, "equipment")])
    add_room_clutter(boxes, "s3_rack", racks)
    for idx, (x, y) in enumerate(((-3.5, 3.5), (0.0, 3.5), (3.5, 3.5), (-3.5, 0.0), (3.5, 0.0), (-3.5, -3.5), (0.0, -3.5), (3.5, -3.5))):
        add_box(boxes, f"s3_core_column_{idx:02d}", (x, y, h / 2), (0.62, 0.62, h), "column", "column")
    for idx, (x, y, yaw) in enumerate(((-14.2, 13.3, 0.25), (-13.2, -13.4, -0.30), (13.6, 13.1, -0.25), (13.4, -13.2, 0.28))):
        add_box(boxes, f"s3_collapse_{idx:02d}", (x, y, 0.85), (2.8, 0.58, 1.7), "debris", "collapse", (0.0, 0.0, yaw))
    return boxes


BUILDERS = {"s1_structured_office": build_s1, "s2_damaged_building": build_s2, "s3_topology_stress": build_s3}


def point_inside_box_xy(x: float, y: float, box: Box, inflation: float) -> bool:
    yaw = box.rpy[2]
    dx, dy = x - box.center[0], y - box.center[1]
    c, s = math.cos(yaw), math.sin(yaw)
    lx, ly = c * dx + s * dy, -s * dx + c * dy
    return abs(lx) <= box.size[0] / 2 + inflation and abs(ly) <= box.size[1] / 2 + inflation


def validate_reachability(boxes: list[Box], scene: SceneSpec, cell=0.25, safety_radius=0.42) -> dict:
    """Validate a 2D flight slice at z=1.5 m; it is geometry QA only."""
    width, height, _ = scene.dimensions_m
    nx, ny = int(width / cell), int(height / cell)
    blocked = set()
    for iy in range(ny):
        y = -height / 2 + (iy + 0.5) * cell
        for ix in range(nx):
            x = -width / 2 + (ix + 0.5) * cell
            for box in boxes:
                z0, z1 = box.center[2] - box.size[2] / 2, box.center[2] + box.size[2] / 2
                if z0 <= 1.5 <= z1 and point_inside_box_xy(x, y, box, safety_radius):
                    blocked.add((ix, iy))
                    break
    sx = int((scene.entry_pose_m[0] + width / 2) / cell)
    sy = int((scene.entry_pose_m[1] + height / 2) / cell)
    if (sx, sy) in blocked:
        raise RuntimeError(f"{scene.key}: entry pose collides after safety inflation")
    todo = [(sx, sy)]
    reached = {(sx, sy)}
    while todo:
        ix, iy = todo.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = ix + dx, iy + dy
            if 0 <= nxt[0] < nx and 0 <= nxt[1] < ny and nxt not in blocked and nxt not in reached:
                reached.add(nxt)
                todo.append(nxt)
    free = nx * ny - len(blocked)
    return {
        "passed": len(reached) / max(1, free) >= 0.985,
        "cell_size_m": cell,
        "safety_radius_m": safety_radius,
        "free_cells": free,
        "reachable_cells": len(reached),
        "reachable_fraction": round(len(reached) / max(1, free), 6),
    }


def world_box_xml(box: Box) -> str:
    r, g, b = MATERIAL_COLORS.get(box.material, MATERIAL_COLORS["wall"])
    roll, pitch, yaw = box.rpy
    sx, sy, sz = box.size
    x, y, z = box.center
    return f"""  <model name='{box.name}'>
    <static>true</static>
    <pose>{x:.4f} {y:.4f} {z:.4f} {roll:.6f} {pitch:.6f} {yaw:.6f}</pose>
    <link name='link'>
      <collision name='collision'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry></collision>
      <visual name='visual'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry><material><ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient><diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse></material></visual>
    </link>
  </model>"""


def write_world(path: Path, scene: SceneSpec, boxes: list[Box]):
    models = "\n".join(world_box_xml(box) for box in boxes)
    write_text_lf(
        path,
        f"""<?xml version='1.0'?>
<sdf version='1.6'>
<world name='{scene.key}'>
  <gravity>0 0 -9.81</gravity>
  <scene><ambient>0.62 0.64 0.66 1</ambient><background>0.72 0.75 0.78 1</background><shadows>true</shadows></scene>
  <include><uri>model://sun</uri></include>
  {models}
</world>
</sdf>
""",
    )


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_preview_png(path: Path, scene: SceneSpec, boxes: list[Box], pixels=1000):
    """Write a simple dependency-free top-down PNG for design review."""
    width = pixels
    height = max(500, round(pixels * scene.dimensions_m[1] / scene.dimensions_m[0]))
    image = bytearray([245, 247, 248] * width * height)
    sx = width / scene.dimensions_m[0]
    sy = height / scene.dimensions_m[1]

    def set_pixel(px: int, py: int, color: tuple[int, int, int]):
        if 0 <= px < width and 0 <= py < height:
            off = (py * width + px) * 3
            image[off:off + 3] = bytes(color)

    def draw_rotated(box: Box, color: tuple[int, int, int]):
        # Rasterize only the box footprint; this is a review preview, not a map.
        hx, hy = box.size[0] / 2, box.size[1] / 2
        radius = math.hypot(hx, hy)
        minx, maxx = box.center[0] - radius, box.center[0] + radius
        miny, maxy = box.center[1] - radius, box.center[1] + radius
        x0, x1 = int((minx + scene.dimensions_m[0] / 2) * sx), int((maxx + scene.dimensions_m[0] / 2) * sx)
        y0, y1 = int((scene.dimensions_m[1] / 2 - maxy) * sy), int((scene.dimensions_m[1] / 2 - miny) * sy)
        yaw = box.rpy[2]
        c, s = math.cos(yaw), math.sin(yaw)
        for py in range(max(0, y0), min(height, y1 + 1)):
            y = scene.dimensions_m[1] / 2 - (py + 0.5) / sy
            for px in range(max(0, x0), min(width, x1 + 1)):
                x = (px + 0.5) / sx - scene.dimensions_m[0] / 2
                dx, dy = x - box.center[0], y - box.center[1]
                lx, ly = c * dx + s * dy, -s * dx + c * dy
                if abs(lx) <= hx and abs(ly) <= hy:
                    set_pixel(px, py, color)

    for box in boxes:
        if box.material == "floor":
            draw_rotated(box, (48, 55, 61))
    palette = {
        "wall": (209, 214, 216), "partition": (161, 174, 181), "column": (101, 118, 128),
        "equipment": (73, 105, 128), "debris": (169, 104, 69), "ceiling": (222, 225, 226),
    }
    for box in boxes:
        if box.material != "floor":
            draw_rotated(box, palette.get(box.material, (180, 180, 180)))
    # Entry marker, the only annotation present in the review image.
    ex = int((scene.entry_pose_m[0] + scene.dimensions_m[0] / 2) * sx)
    ey = int((scene.dimensions_m[1] / 2 - scene.entry_pose_m[1]) * sy)
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            if dx * dx + dy * dy <= 64:
                set_pixel(ex + dx, ey + dy, (35, 190, 95))
    raw = b"".join(b"\x00" + bytes(image[row * width * 3:(row + 1) * width * 3]) for row in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b""))


def generate(scene: SceneSpec):
    boxes = BUILDERS[scene.key](scene)
    validation = validate_reachability(boxes, scene)
    if not validation["passed"]:
        raise RuntimeError(f"{scene.key} is not sufficiently connected: {validation}")
    stem = scene.title.replace(" ", "-")
    world = ROOT / "gazebo" / "worlds" / f"{stem}.world"
    pcd = ROOT / "maps" / "pcd" / f"{stem}.pcd"
    obj = ROOT / "meshes" / "obj" / f"{stem}.obj"
    dae = ROOT / "meshes" / "dae" / f"{stem}.dae"
    preview = ROOT / "validation" / "previews" / f"{stem}.png"
    report = ROOT / "validation" / f"{stem}.json"
    for path in (world, pcd, obj, dae, preview, report):
        path.parent.mkdir(parents=True, exist_ok=True)
    write_world(world, scene, boxes)
    write_mtl(ROOT / "meshes" / "obj" / "ruins_urban_01.mtl")
    points = write_pcd(pcd, boxes, PCD_STEP_M)
    write_obj(obj, boxes, "ruins_urban_01.mtl")
    write_dae(dae, boxes)
    write_preview_png(preview, scene, boxes)
    write_text_lf(report, json.dumps({"scene": asdict(scene), "box_count": len(boxes), "pcd_points": points, "reachability": validation, "runtime_inputs": {"workspace_boundary_only": True, "truth_assets_offline_only": True, "route_or_goal_prior": False}}, indent=2))
    return {"scene": scene.key, "preview": str(preview), "world": str(world), "pcd": str(pcd), "obj": str(obj), "dae": str(dae), "validation": validation, "pcd_points": points}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=[scene.key for scene in SCENES] + ["all"], default="all")
    args = parser.parse_args()
    wanted = SCENES if args.scene == "all" else tuple(scene for scene in SCENES if scene.key == args.scene)
    results = [generate(scene) for scene in wanted]
    write_text_lf(ROOT / "validation" / "Building-Interior-benchmark-summary.json", json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
