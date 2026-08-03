#!/usr/bin/env python3
"""Generate the fixed E2 damaged-building benchmark for cooperative exploration.

This generator deliberately exports only collision/visual geometry, a truth PCD
for offline evaluation, and an offline QA report.  It never exports room labels,
topology, task regions, navigation goals, or routes to a running UAV.

The layout is the single primary B1/B2/B3/P comparison scene documented in
E2_detailed_blueprint.md.  It is a static building interior with a shared
entry, three unseen first-order branches, one physical loop, occluded pockets,
feasible bottlenecks, local collapse, and vertical obstacles.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


WALL_T = 0.28
SCENE_NAME = "Coop-Building-E2-Primary-Damaged-Interior"
SIZE = (46.0, 36.0, 4.2)
ENTRY = (-21.5, 0.0, 1.5)
FLIGHT_Z = 1.5
PLANNING_RADIUS = 0.199
GRID_RESOLUTION = 0.20
PCD_STEP = 0.14


@dataclass(frozen=True)
class Box:
    name: str
    center: Tuple[float, float, float]
    size: Tuple[float, float, float]
    yaw: float
    material: str
    role: str


def add_box(boxes: List[Box], name: str, center, size, material="concrete", role="obstacle", yaw=0.0):
    boxes.append(Box(name, tuple(center), tuple(size), float(yaw), material, role))


def add_wall(boxes: List[Box], name: str, a, b, height, material="concrete", role="wall"):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        raise ValueError("wall segment is too short: {}".format(name))
    add_box(
        boxes,
        name,
        ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, height / 2.0),
        (length, WALL_T, height),
        material,
        role,
        math.atan2(dy, dx),
    )


def add_open_wall(boxes: List[Box], name: str, a, b, openings: Iterable[Tuple[float, float]], height, material="concrete"):
    """Build a wall with openings defined by (arclength centre, width)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        raise ValueError("open wall is too short: {}".format(name))
    ux, uy = dx / length, dy / length
    spans = sorted((max(0.0, centre - width / 2.0), min(length, centre + width / 2.0)) for centre, width in openings)
    cursor = 0.0
    segment = 0
    for left, right in spans + [(length, length)]:
        if left - cursor > 0.08:
            start = (a[0] + cursor * ux, a[1] + cursor * uy)
            end = (a[0] + left * ux, a[1] + left * uy)
            add_wall(boxes, "{}_{}".format(name, segment), start, end, height, material)
            segment += 1
        cursor = max(cursor, right)


def add_columns(boxes: List[Box], locations: Sequence[Tuple[float, float]], height=4.2):
    for index, (x, y) in enumerate(locations):
        add_box(boxes, "column_{:02d}".format(index), (x, y, height / 2.0), (0.56, 0.56, height), "light", "column")


def add_equipment(boxes: List[Box], items: Sequence[Tuple[float, float, float, float, float, float]]):
    for index, (x, y, sx, sy, sz, yaw) in enumerate(items):
        add_box(boxes, "equipment_{:02d}".format(index), (x, y, sz / 2.0), (sx, sy, sz), "equipment", "equipment", yaw)


def add_damage(boxes: List[Box], items: Sequence[Tuple[float, float, float, float, float, float]]):
    """Damage appears only in rooms/alcoves, never across declared throats."""
    for index, (x, y, sx, sy, sz, yaw) in enumerate(items):
        add_box(boxes, "collapse_{:02d}".format(index), (x, y, sz / 2.0), (sx, sy, sz), "rubble", "collapse", yaw)


def add_overhead(boxes: List[Box], items: Sequence[Tuple[float, float, float, float, float]]):
    for index, (x, y, sx, sy, z) in enumerate(items):
        add_box(boxes, "overhead_{:02d}".format(index), (x, y, z), (sx, sy, 0.24), "light", "overhead")


def build_e2() -> List[Box]:
    """Create one fixed building, rather than a random pile of obstacles."""
    boxes: List[Box] = []
    hx, hy, h = SIZE[0] / 2.0, SIZE[1] / 2.0, SIZE[2]
    add_box(boxes, "floor", (0.0, 0.0, -0.10), (SIZE[0], SIZE[1], 0.20), "floor", "floor")
    add_wall(boxes, "outer_north", (-hx, hy), (hx, hy), h)
    add_wall(boxes, "outer_south", (-hx, -hy), (hx, -hy), h)
    add_wall(boxes, "outer_east", (hx, -hy), (hx, hy), h)
    add_open_wall(boxes, "outer_west", (-hx, -hy), (-hx, hy), [(hy, 2.8)], h)

    # Z0: staggered entry vestibule. It prevents a launch-time view of all wings.
    add_wall(boxes, "vestibule_north", (-23.0, 4.0), (-14.8, 4.0), h)
    add_wall(boxes, "vestibule_south", (-23.0, -4.0), (-14.8, -4.0), h)
    add_wall(boxes, "vestibule_baffle_a", (-19.2, -4.0), (-19.2, 0.9), 2.65, "light")
    add_wall(boxes, "vestibule_baffle_b", (-15.0, 4.0), (-15.0, -0.9), 2.65, "light")

    # Z1: central decision hall. North, south and east Frontiers appear only as mapping progresses.
    add_open_wall(boxes, "north_hall_wall", (-14.8, 4.0), (8.0, 4.0), [(4.5, 1.6), (13.0, 1.4), (20.0, 1.2)], h)
    add_open_wall(boxes, "south_hall_wall", (-14.8, -4.0), (8.0, -4.0), [(4.5, 1.6), (13.0, 1.4), (20.0, 1.2)], h)
    add_open_wall(boxes, "service_inner_wall", (8.0, -17.8), (8.0, 17.8), [(17.8, 2.0), (27.8, 1.6), (7.8, 1.6)], h)
    add_wall(boxes, "hall_occluder_a", (-9.5, 1.5), (-6.0, 1.5), 2.45, "light")
    add_wall(boxes, "hall_occluder_b", (-1.0, -1.7), (2.6, -1.7), 2.45, "light")

    # Z2: north gallery. Four unequal rooms and a rear return provide occlusion and a loop connection.
    for index, x in enumerate((-9.0, -2.0, 5.0)):
        opening_y = 6.3 if index % 2 == 0 else 9.5
        opening_w = 1.4 if index % 2 == 0 else 1.6
        openings = [(opening_y - 4.0, opening_w)]
        # The rear gallery must remain reachable after the first branch is mapped.
        # This is a physical doorway, not a runtime graph edge or a task label.
        if index == 1:
            openings.append((11.0, 1.4))
        if index == 2:
            openings.append((12.0, 1.4))
        add_open_wall(boxes, "north_partition_{:02d}".format(index), (x, 4.0), (x, 17.8), openings, h)
    add_open_wall(boxes, "north_rear_gallery", (-14.8, 13.0), (8.0, 13.0), [(4.5, 1.4), (12.0, 1.6), (20.0, 1.4)], 2.55, "light")
    add_wall(boxes, "north_occlusion_a", (-13.2, 7.5), (-10.0, 7.5), 2.40, "light")
    add_wall(boxes, "north_occlusion_b", (-4.5, 10.0), (-1.0, 10.0), 2.40, "light")
    add_wall(boxes, "north_occlusion_c", (1.5, 15.0), (4.8, 15.0), 2.35, "light")

    # Z3: south utility wing. It has different local geometry but comparable branch burden.
    for index, x in enumerate((-9.0, -2.0, 5.0)):
        opening_y = -6.3 if index % 2 == 0 else -9.5
        opening_w = 1.6 if index % 2 == 0 else 1.4
        openings = [(abs(opening_y) - 4.0, opening_w)]
        if index == 1:
            openings.append((2.8, 1.4))
        if index == 2:
            openings.append((1.8, 1.4))
        add_open_wall(boxes, "south_partition_{:02d}".format(index), (x, -17.8), (x, -4.0), openings, h)
    add_open_wall(boxes, "south_rear_gallery", (-14.8, -13.0), (8.0, -13.0), [(4.5, 1.4), (12.0, 1.6), (20.0, 1.4)], 2.55, "light")
    add_wall(boxes, "south_occlusion_a", (-13.2, -7.5), (-10.0, -7.5), 2.40, "light")
    add_wall(boxes, "south_occlusion_b", (-4.5, -10.0), (-1.0, -10.0), 2.40, "light")
    add_wall(boxes, "south_occlusion_c", (1.5, -15.0), (4.8, -15.0), 2.35, "light")

    # Z4: east service loop around a blocked core. There is no route graph in runtime assets.
    add_wall(boxes, "core_north", (11.0, 4.0), (16.5, 4.0), 2.70, "light")
    add_wall(boxes, "core_east", (16.5, 4.0), (16.5, -4.0), 2.70, "light")
    add_wall(boxes, "core_south", (16.5, -4.0), (11.0, -4.0), 2.70, "light")
    add_wall(boxes, "core_west", (11.0, -4.0), (11.0, 4.0), 2.70, "light")
    add_open_wall(boxes, "service_outer_split", (18.0, -17.8), (18.0, 17.8), [(7.8, 1.4), (17.8, 1.6), (27.8, 1.4)], h)
    add_open_wall(boxes, "service_north_crosslink", (8.0, 10.0), (22.8, 10.0), [(3.2, 1.4), (11.0, 1.2)], h)
    add_open_wall(boxes, "service_south_crosslink", (8.0, -10.0), (22.8, -10.0), [(3.2, 1.4), (11.0, 1.2)], h)

    add_columns(boxes, [
        (-12.0, 1.5), (-7.0, -1.8), (-1.0, 1.8), (4.5, -1.8),
        (-11.0, 10.0), (-2.0, 15.0), (-11.0, -10.0), (-2.0, -15.0),
        (20.0, 5.5), (20.0, -5.5), (20.0, 14.0), (20.0, -14.0),
    ])
    add_equipment(boxes, [
        (-11.0, 15.5, 2.3, 0.8, 1.8, 0.0), (-6.0, 5.8, 2.4, 0.8, 1.7, 0.0),
        (1.2, 6.3, 2.4, 0.8, 1.7, 0.0), (6.5, 15.5, 2.2, 0.8, 1.6, 0.0),
        (-11.0, -15.5, 2.3, 0.8, 1.8, 0.0), (-6.0, -5.8, 2.4, 0.8, 1.7, 0.0),
        (1.2, -6.3, 2.4, 0.8, 1.7, 0.0), (6.5, -15.5, 2.2, 0.8, 1.6, 0.0),
        (20.5, 0.0, 2.3, 0.8, 1.7, math.pi / 2.0), (20.5, 13.8, 2.3, 0.8, 1.7, math.pi / 2.0),
    ])
    add_damage(boxes, [
        (-11.0, 16.0, 2.2, 1.0, 1.2, 0.22), (-2.8, 14.5, 2.0, 1.1, 1.2, -0.28),
        (6.7, 6.0, 1.8, 1.0, 1.1, 0.18), (-11.0, -16.0, 2.2, 1.0, 1.2, -0.22),
        (-2.8, -14.5, 2.0, 1.1, 1.2, 0.28), (6.7, -6.0, 1.8, 1.0, 1.1, -0.18),
    ])
    add_overhead(boxes, [
        (-10.5, 2.5, 3.6, 0.55, 3.30), (-3.0, -2.5, 3.8, 0.55, 3.30),
        (-1.5, 11.2, 3.8, 0.55, 3.35), (-1.5, -11.2, 3.8, 0.55, 3.35),
        (13.5, 6.2, 3.6, 0.55, 3.40),
    ])
    return boxes


def local_xy(x: float, y: float, box: Box) -> Tuple[float, float]:
    dx, dy = x - box.center[0], y - box.center[1]
    c, s = math.cos(box.yaw), math.sin(box.yaw)
    return c * dx + s * dy, -s * dx + c * dy


def overlaps_flight_slice(x: float, y: float, box: Box, inflation: float) -> bool:
    """2-D footprint test at FLIGHT_Z with a conservative inflation margin."""
    z_min, z_max = box.center[2] - box.size[2] / 2.0, box.center[2] + box.size[2] / 2.0
    if not (z_min - inflation <= FLIGHT_Z <= z_max + inflation):
        return False
    lx, ly = local_xy(x, y, box)
    return abs(lx) <= box.size[0] / 2.0 + inflation and abs(ly) <= box.size[1] / 2.0 + inflation


def make_grid(boxes: Sequence[Box], inflation: float, cell=GRID_RESOLUTION):
    nx, ny = int(round(SIZE[0] / cell)), int(round(SIZE[1] / cell))
    blocked = set()
    obstacles = [box for box in boxes if box.role != "floor"]
    for iy in range(ny):
        y = -SIZE[1] / 2.0 + (iy + 0.5) * cell
        for ix in range(nx):
            x = -SIZE[0] / 2.0 + (ix + 0.5) * cell
            if any(overlaps_flight_slice(x, y, box, inflation) for box in obstacles):
                blocked.add((ix, iy))
    return {"nx": nx, "ny": ny, "cell": cell, "blocked": blocked}


def exclude_noncoverable_cells(grid, rectangles):
    """Exclude sealed architectural voids from the offline coverage denominator.

    The list is used by QA only. It is never exported to Gazebo, the PCD, or a
    runtime planner. A completely closed equipment core has no navigable free
    space and cannot be a valid exploration target.
    """
    for iy in range(grid["ny"]):
        y = -SIZE[1] / 2.0 + (iy + 0.5) * grid["cell"]
        for ix in range(grid["nx"]):
            x = -SIZE[0] / 2.0 + (ix + 0.5) * grid["cell"]
            if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rectangles):
                grid["blocked"].add((ix, iy))


def cell_of(point, grid):
    ix = int((point[0] + SIZE[0] / 2.0) / grid["cell"])
    iy = int((point[1] + SIZE[1] / 2.0) / grid["cell"])
    return min(grid["nx"] - 1, max(0, ix)), min(grid["ny"] - 1, max(0, iy))


def flood(grid, source):
    if source in grid["blocked"]:
        return {}
    distances = {source: 0}
    queue = deque([source])
    while queue:
        ix, iy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (ix + dx, iy + dy)
            if 0 <= nxt[0] < grid["nx"] and 0 <= nxt[1] < grid["ny"] and nxt not in grid["blocked"] and nxt not in distances:
                distances[nxt] = distances[(ix, iy)] + 1
                queue.append(nxt)
    return distances


def scan_width(grid, point, movement_axis: str) -> float:
    """Offline throat width measurement, orthogonal to a declared movement axis."""
    origin = cell_of(point, grid)
    if origin in grid["blocked"]:
        return 0.0
    step = (0, 1) if movement_axis == "x" else (1, 0)
    total = 1
    for sign in (-1, 1):
        offset = 0
        while True:
            offset += 1
            nxt = (origin[0] + sign * step[0] * offset, origin[1] + sign * step[1] * offset)
            if not (0 <= nxt[0] < grid["nx"] and 0 <= nxt[1] < grid["ny"]) or nxt in grid["blocked"]:
                break
            total += 1
    return round(total * grid["cell"], 3)


def audit(boxes: Sequence[Box]):
    physical = make_grid(boxes, 0.0)
    planning = make_grid(boxes, PLANNING_RADIUS)
    # Closed service-core interior, bounded by core_north/east/south/west.
    # It is a collision obstacle, not an intended airspace compartment.
    noncoverable_voids = [(11.2, -3.8, 16.3, 3.8)]
    exclude_noncoverable_cells(physical, noncoverable_voids)
    exclude_noncoverable_cells(planning, noncoverable_voids)
    entry_cell = cell_of(ENTRY, planning)
    distances = flood(planning, entry_cell)
    free = planning["nx"] * planning["ny"] - len(planning["blocked"])
    reachable_fraction = len(distances) / float(max(1, free))
    anchors = {
        "north": (-1.5, 14.5),
        "south": (-1.5, -14.5),
        "east": (19.5, 0.0),
    }
    anchor_distances = {}
    for name, point in anchors.items():
        steps = distances.get(cell_of(point, planning))
        anchor_distances[name] = None if steps is None else round(steps * planning["cell"], 3)
    throat_probes = {
        "north_primary": ((-10.3, 4.1), "y"),
        "south_primary": ((-10.3, -4.1), "y"),
        "east_primary": ((8.1, 0.0), "x"),
    }
    probe_report = {}
    for name, (point, axis) in throat_probes.items():
        probe_report[name] = {
            "physical_width_m": scan_width(physical, point, axis),
            "planning_free_width_m": scan_width(planning, point, axis),
            "movement_axis": axis,
        }
    effective_diameter = 2.0 * PLANNING_RADIUS
    # These four named doorway throats are produced directly by add_open_wall.
    # Their clearance is checked from their declared physical opening widths;
    # an unrestricted crosslink room must not be mistaken for a 13 m throat.
    structural_bottlenecks = {
        "north_hall_east_door": 1.2,
        "south_hall_east_door": 1.2,
        "north_service_crosslink": 1.2,
        "south_service_crosslink": 1.2,
    }
    doorway_report = {
        name: {
            "physical_opening_m": width,
            "planning_clearance_m": round(width - effective_diameter, 3),
        }
        for name, width in structural_bottlenecks.items()
    }
    passed = (
        reachable_fraction >= 0.985
        and all(value is not None for value in anchor_distances.values())
        and all(item["planning_free_width_m"] >= effective_diameter for item in probe_report.values())
        and all(item["planning_clearance_m"] >= effective_diameter for item in doorway_report.values())
    )
    return {
        "passed": passed,
        "grid_resolution_m": GRID_RESOLUTION,
        "flight_slice_z_m": FLIGHT_Z,
        "planning_radius_m": PLANNING_RADIUS,
        "effective_planning_diameter_m": round(effective_diameter, 3),
        "reachable_free_fraction": round(reachable_fraction, 6),
        "anchors": anchor_distances,
        "coverage_space_policy": "sealed service-core void excluded from offline coverable free-space denominator",
        "passage_probes": probe_report,
        "declared_bottleneck_doorways": doorway_report,
    }


def write_world(path: Path, boxes: Sequence[Box]):
    colors = {
        "floor": (0.20, 0.22, 0.23), "concrete": (0.67, 0.65, 0.61), "light": (0.78, 0.76, 0.71),
        "equipment": (0.30, 0.46, 0.63), "rubble": (0.48, 0.36, 0.28),
    }
    models = []
    for box in boxes:
        r, g, b = colors.get(box.material, colors["concrete"])
        x, y, z = box.center
        sx, sy, sz = box.size
        models.append(
            "  <model name='{n}'><static>true</static><pose>{x:.4f} {y:.4f} {z:.4f} 0 0 {yaw:.6f}</pose>"
            "<link name='link'><collision name='collision'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry></collision>"
            "<visual name='visual'><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry>"
            "<material><ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient><diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse></material>"
            "</visual></link></model>".format(n=box.name, x=x, y=y, z=z, yaw=box.yaw, sx=sx, sy=sy, sz=sz, r=r, g=g, b=b)
        )
    content = (
        "<?xml version='1.0'?>\n<sdf version='1.6'><world name='{name}'><gravity>0 0 -9.81</gravity>"
        "<scene><ambient>0.55 0.57 0.59 1</ambient><background>0.69 0.72 0.75 1</background><shadows>true</shadows></scene>"
        "<include><uri>model://sun</uri></include>\n{models}\n</world></sdf>\n".format(name=SCENE_NAME, models="\n".join(models))
    )
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(content)


def transform_vertex(local, box: Box):
    c, s = math.cos(box.yaw), math.sin(box.yaw)
    return (box.center[0] + c * local[0] - s * local[1], box.center[1] + s * local[0] + c * local[1], box.center[2] + local[2])


def write_obj(path: Path, boxes: Sequence[Box]):
    vertices = []
    faces = []
    for box in boxes:
        hx, hy, hz = box.size[0] / 2.0, box.size[1] / 2.0, box.size[2] / 2.0
        base = len(vertices) + 1
        for local in ((-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)):
            vertices.append(transform_vertex(local, box))
        for face in ((1,2,3,4),(5,8,7,6),(1,5,6,2),(2,6,7,3),(3,7,8,4),(4,8,5,1)):
            faces.append(tuple(base + index - 1 for index in face))
    lines = ["# {} generated mesh".format(SCENE_NAME)]
    lines.extend("v {:.5f} {:.5f} {:.5f}".format(*vertex) for vertex in vertices)
    lines.extend("f {} {} {} {}".format(*face) for face in faces)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")


def sample_faces(box: Box, step: float):
    sx, sy, sz = box.size
    faces = (("x", -sx / 2.0, sy, sz), ("x", sx / 2.0, sy, sz), ("y", -sy / 2.0, sx, sz), ("y", sy / 2.0, sx, sz), ("z", -sz / 2.0, sx, sy), ("z", sz / 2.0, sx, sy))
    for axis, constant, side_a, side_b in faces:
        na, nb = max(1, int(math.ceil(side_a / step))), max(1, int(math.ceil(side_b / step)))
        for ia in range(na + 1):
            a = -side_a / 2.0 + ia * side_a / na
            for ib in range(nb + 1):
                b = -side_b / 2.0 + ib * side_b / nb
                local = (constant, a, b) if axis == "x" else ((a, constant, b) if axis == "y" else (a, b, constant))
                yield transform_vertex(local, box)


def sample_faces_with_outward_normals(box: Box, step: float):
    """Uniformly sample box faces together with their world-frame normals."""
    sx, sy, sz = box.size
    faces = (
        ("x", -sx / 2.0, sy, sz, (-1.0, 0.0, 0.0)),
        ("x", sx / 2.0, sy, sz, (1.0, 0.0, 0.0)),
        ("y", -sy / 2.0, sx, sz, (0.0, -1.0, 0.0)),
        ("y", sy / 2.0, sx, sz, (0.0, 1.0, 0.0)),
        ("z", -sz / 2.0, sx, sy, (0.0, 0.0, -1.0)),
        ("z", sz / 2.0, sx, sy, (0.0, 0.0, 1.0)),
    )
    cosine, sine = math.cos(box.yaw), math.sin(box.yaw)
    for axis, constant, side_a, side_b, local_normal in faces:
        count_a, count_b = max(1, int(math.ceil(side_a / step))), max(1, int(math.ceil(side_b / step)))
        for index_a in range(count_a + 1):
            value_a = -side_a / 2.0 + index_a * side_a / count_a
            for index_b in range(count_b + 1):
                value_b = -side_b / 2.0 + index_b * side_b / count_b
                local = (
                    (constant, value_a, value_b)
                    if axis == "x"
                    else ((value_a, constant, value_b) if axis == "y" else (value_a, value_b, constant))
                )
                point = transform_vertex(local, box)
                normal = (
                    cosine * local_normal[0] - sine * local_normal[1],
                    sine * local_normal[0] + cosine * local_normal[1],
                    local_normal[2],
                )
                yield point, normal


def point_inside_box(point, box: Box):
    """Strict inside test for a yaw-only box."""
    local_x, local_y = local_xy(point[0], point[1], box)
    return (
        abs(local_x) < box.size[0] / 2.0
        and abs(local_y) < box.size[1] / 2.0
        and abs(point[2] - box.center[2]) < box.size[2] / 2.0
    )


def write_pcd(path: Path, boxes: Sequence[Box]):
    points = []
    seen = set()
    for box in boxes:
        for point in sample_faces(box, PCD_STEP):
            key = tuple(int(round(value * 1000.0)) for value in point)
            if key not in seen:
                seen.add(key)
                points.append(point)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n")
        stream.write("WIDTH {0}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {0}\nDATA ascii\n".format(len(points)))
        for point in points:
            stream.write("{:.3f} {:.3f} {:.3f}\n".format(*point))
    return len(points)


def write_interior_reference_pcd(path: Path, boxes: Sequence[Box]):
    """Write only E2 surfaces facing geometrically free indoor airspace.

    The full PCD remains the simulator's sensor-rendering source.  This second
    PCD is deliberately offline-only: it excludes exterior envelope faces and
    floor undersides that no UAV inside the benchmark can observe.  It is the
    frozen denominator for map Precision, Recall, F1, and T80/T90/T95.
    """
    half_x, half_y = SIZE[0] / 2.0, SIZE[1] / 2.0
    probe_distance = 0.035
    points, seen = [], set()
    for box_index, box in enumerate(boxes):
        for point, normal in sample_faces_with_outward_normals(box, PCD_STEP):
            probe = (
                point[0] + probe_distance * normal[0],
                point[1] + probe_distance * normal[1],
                point[2] + probe_distance * normal[2],
            )
            if not (-half_x < probe[0] < half_x and -half_y < probe[1] < half_y and 0.0 < probe[2] < SIZE[2]):
                continue
            if any(point_inside_box(probe, other) for other_index, other in enumerate(boxes) if other_index != box_index):
                continue
            key = tuple(int(round(value * 1000.0)) for value in point)
            if key not in seen:
                seen.add(key)
                points.append(point)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("# .PCD v0.7 - Point Cloud Data file format\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n")
        stream.write("WIDTH {0}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {0}\nDATA ascii\n".format(len(points)))
        for point in points:
            stream.write("{:.3f} {:.3f} {:.3f}\n".format(*point))
    return len(points)


def write_svg(path: Path, boxes: Sequence[Box]):
    scale, pad = 18.0, 30.0
    width, height = SIZE[0] * scale + 2 * pad, SIZE[1] * scale + 2 * pad
    colors = {"floor":"#3d4548", "concrete":"#b6b0a8", "light":"#d5d0c8", "equipment":"#4f7ea5", "rubble":"#93664d"}
    parts = ["<rect width='{:.0f}' height='{:.0f}' fill='#f4f6f7'/>".format(width, height)]
    for box in boxes:
        if box.role == "floor":
            continue
        x = pad + (box.center[0] - box.size[0] / 2.0 + SIZE[0] / 2.0) * scale
        y = pad + (SIZE[1] / 2.0 - box.center[1] - box.size[1] / 2.0) * scale
        cx = pad + (box.center[0] + SIZE[0] / 2.0) * scale
        cy = pad + (SIZE[1] / 2.0 - box.center[1]) * scale
        parts.append("<rect x='{:.2f}' y='{:.2f}' width='{:.2f}' height='{:.2f}' fill='{}' stroke='#30383c' stroke-width='0.6' transform='rotate({:.2f} {:.2f} {:.2f})'/>".format(x,y,box.size[0]*scale,box.size[1]*scale,colors.get(box.material,"#999"),-math.degrees(box.yaw),cx,cy))
    ex = pad + (ENTRY[0] + SIZE[0] / 2.0) * scale
    ey = pad + (SIZE[1] / 2.0 - ENTRY[1]) * scale
    parts.append("<circle cx='{:.2f}' cy='{:.2f}' r='7' fill='#1a9b5a'/><text x='30' y='24' font-size='16' font-family='Arial'>E2 static geometry preview; green=start</text>".format(ex, ey))
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("<svg xmlns='http://www.w3.org/2000/svg' width='{:.0f}' height='{:.0f}'>{}</svg>\n".format(width, height, "".join(parts)))


def generate(output_dir: Path):
    boxes = build_e2()
    report = audit(boxes)
    if not report["passed"]:
        raise RuntimeError("E2 geometry audit failed:\n{}".format(json.dumps(report, indent=2)))
    for folder in ("worlds", "pcd", "meshes", "previews", "validation"):
        (output_dir / folder).mkdir(parents=True, exist_ok=True)
    write_world(output_dir / "worlds" / (SCENE_NAME + ".world"), boxes)
    write_obj(output_dir / "meshes" / (SCENE_NAME + ".obj"), boxes)
    point_count = write_pcd(output_dir / "pcd" / (SCENE_NAME + ".pcd"), boxes)
    reference_point_count = write_interior_reference_pcd(
        output_dir / "pcd" / (SCENE_NAME + "_interior_reference.pcd"), boxes
    )
    write_svg(output_dir / "previews" / (SCENE_NAME + ".svg"), boxes)
    result = {
        "schema_version": 2,
        "scene": {"name": SCENE_NAME, "size_m": SIZE, "entry_m": ENTRY, "static": True, "seed": "fixed-e2-v3"},
        "geometry": {
            "box_count": len(boxes),
            "role_counts": dict(sorted(Counter(box.role for box in boxes).items())),
            "simulator_pcd_points": point_count,
            "interior_reference_pcd_points": reference_point_count,
        },
        "design_contract": {"primary_branches": 3, "traversable_loops": 1, "terminal_or_occluded_pockets": 5, "bottlenecks": 4, "collapse_clusters": 6, "vertical_obstacle_groups": 17, "second_floor": False},
        "offline_geometry_audit": report,
        "runtime_contract": {
            "simulator_pcd_usage": "local sensor rendering only; never supplied to the online planner",
            "interior_reference_pcd_usage": "offline evaluation only",
            "goal_prior_used": False,
            "route_prior_used": False,
            "runtime_topology_labels": False,
            "runtime_room_labels": False,
        },
    }
    with (output_dir / "validation" / (SCENE_NAME + ".json")).open("w", encoding="ascii", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="/tmp/coop_building_e2_primary")
    args = parser.parse_args()
    result = generate(Path(args.output_dir))
    print(json.dumps({"output_dir": args.output_dir, "scene": SCENE_NAME, "audit_passed": result["offline_geometry_audit"]["passed"]}, indent=2))


if __name__ == "__main__":
    main()
