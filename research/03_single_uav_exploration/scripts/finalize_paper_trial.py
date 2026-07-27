#!/usr/bin/env python3
"""Archive one completed trial and generate reproducible paper artifacts."""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path


VARIANT_BOUNDS = {
    "base": [-20.65, -15.65, 0.35, 20.65, 15.65, 2.65],
    "medium": [-20.65, -15.65, 0.35, 20.65, 15.65, 5.00],
    "complex": [-20.65, -15.65, 0.35, 20.65, 15.65, 5.00],
}

HEIGHT_COLORS = [
    "#440154",
    "#482878",
    "#3e4989",
    "#31688e",
    "#26828e",
    "#1f9e89",
    "#35b779",
    "#6ece58",
    "#b5de2b",
    "#fde725",
]


def read_ascii_pcd(path, bounds=None):
    points = []
    data_found = False
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if not data_found:
                if stripped == "DATA ascii":
                    data_found = True
                elif stripped.startswith("DATA "):
                    raise ValueError("only ASCII PCD is supported: {}".format(path))
                continue
            if not stripped:
                continue
            values = stripped.split()
            if len(values) < 3:
                continue
            point = tuple(float(values[index]) for index in range(3))
            if not all(math.isfinite(value) for value in point):
                continue
            if bounds is not None and not all(
                bounds[index] <= point[index] <= bounds[index + 3]
                for index in range(3)
            ):
                continue
            points.append(point)
    if not data_found:
        raise ValueError("missing DATA ascii header: {}".format(path))
    if not points:
        raise ValueError("PCD contains no points inside the evaluation volume: {}".format(path))
    return points


def voxelize(points, resolution):
    return {
        tuple(int(round(value / resolution)) for value in point)
        for point in points
    }


def neighbor_offsets(tolerance):
    offsets = []
    limit_squared = tolerance * tolerance
    for x_value in range(-tolerance, tolerance + 1):
        for y_value in range(-tolerance, tolerance + 1):
            for z_value in range(-tolerance, tolerance + 1):
                if x_value * x_value + y_value * y_value + z_value * z_value <= limit_squared:
                    offsets.append((x_value, y_value, z_value))
    return offsets


def matched_count(source, target, offsets):
    return sum(
        any(
            (
                voxel[0] + offset[0],
                voxel[1] + offset[1],
                voxel[2] + offset[2],
            )
            in target
            for offset in offsets
        )
        for voxel in source
    )


def evaluate(truth_points, observed_points, resolution, tolerance, bounds):
    truth = voxelize(truth_points, resolution)
    observed = voxelize(observed_points, resolution)
    offsets = neighbor_offsets(tolerance)
    truth_matched = matched_count(truth, observed, offsets)
    observed_matched = matched_count(observed, truth, offsets)
    recall = truth_matched / len(truth)
    precision = observed_matched / len(observed)
    f1_score = (
        0.0
        if precision + recall == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )
    return {
        "schema_version": 1,
        "metric": "occupied_surface_voxel_coverage",
        "resolution_m": resolution,
        "tolerance_voxels": tolerance,
        "evaluation_bounds_m": bounds,
        "truth_voxels": len(truth),
        "observed_voxels": len(observed),
        "matched_truth_voxels": truth_matched,
        "matched_observed_voxels": observed_matched,
        "surface_recall": round(recall, 6),
        "surface_precision": round(precision, 6),
        "surface_f1": round(f1_score, 6),
        "important_limit": (
            "Simulator truth was read only after exploration. This occupied-surface "
            "metric is intended for controlled comparisons, not as free-space coverage."
        ),
    }


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def max_height_grid(points, resolution):
    grid = {}
    for x_value, y_value, z_value in points:
        key = (
            int(round(x_value / resolution)),
            int(round(y_value / resolution)),
        )
        grid[key] = max(grid.get(key, z_value), z_value)
    return grid


def svg_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def height_color(z_value, minimum, maximum):
    if maximum <= minimum:
        return HEIGHT_COLORS[0]
    ratio = max(0.0, min(1.0, (z_value - minimum) / (maximum - minimum)))
    index = min(len(HEIGHT_COLORS) - 1, int(ratio * len(HEIGHT_COLORS)))
    return HEIGHT_COLORS[index]


def grid_path(cells, color, bounds, panel_x, panel_y, panel_width, panel_height):
    min_x = int(math.floor(bounds[0]))
    min_y = int(math.floor(bounds[1]))
    max_x = int(math.ceil(bounds[3]))
    max_y = int(math.ceil(bounds[4]))
    x_span = max(1, max_x - min_x + 1)
    y_span = max(1, max_y - min_y + 1)
    cell_width = panel_width / x_span
    cell_height = panel_height / y_span
    commands = []
    for x_index, y_index in cells:
        x_value = panel_x + (x_index - min_x) * cell_width
        y_value = panel_y + panel_height - (y_index - min_y + 1) * cell_height
        commands.append(
            "M{:.2f},{:.2f}h{:.2f}v{:.2f}h-{:.2f}z".format(
                x_value,
                y_value,
                cell_width + 0.15,
                cell_height + 0.15,
                cell_width + 0.15,
            )
        )
    if not commands:
        return ""
    return '<path fill="{}" d="{}"/>'.format(color, "".join(commands))


def write_topdown_svg(path, truth_points, observed_points, bounds, resolution, runtime, coverage):
    truth_grid = max_height_grid(truth_points, resolution)
    observed_grid = max_height_grid(observed_points, resolution)
    all_heights = list(truth_grid.values()) + list(observed_grid.values())
    min_height = min(all_heights)
    max_height = max(all_heights)

    width = 2100
    height = 780
    margin = 70
    gap = 55
    panel_width = (width - 2 * margin - 2 * gap) / 3
    panel_height = 500
    panel_y = 120
    panel_x_values = [
        margin,
        margin + panel_width + gap,
        margin + 2 * (panel_width + gap),
    ]

    min_ix = int(math.floor(bounds[0] / resolution))
    min_iy = int(math.floor(bounds[1] / resolution))
    max_ix = int(math.ceil(bounds[3] / resolution))
    max_iy = int(math.ceil(bounds[4] / resolution))
    index_bounds = [min_ix, min_iy, 0, max_ix, max_iy, 0]

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
        'viewBox="0 0 {} {}">'.format(width, height, width, height),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{{font-family:Arial,sans-serif;fill:#202124}}'
        '.title{{font-size:34px;font-weight:700}}'
        '.panel{{font-size:25px;font-weight:700}}'
        '.small{{font-size:19px}}'
        '.metric{{font-size:21px;font-weight:600}}</style>',
        '<text class="title" x="{}" y="48">Single-UAV 3D Mapping Result</text>'.format(margin),
    ]

    panel_titles = [
        "(a) Simulator truth",
        "(b) Online reconstruction",
        "(c) Top-down difference",
    ]
    for panel_x, title in zip(panel_x_values, panel_titles):
        svg.append(
            '<text class="panel" x="{:.1f}" y="96">{}</text>'.format(
                panel_x, svg_escape(title)
            )
        )
        svg.append(
            '<rect x="{:.1f}" y="{}" width="{:.1f}" height="{}" '
            'fill="#f7f8fa" stroke="#4a4a4a" stroke-width="2"/>'.format(
                panel_x, panel_y, panel_width, panel_height
            )
        )

    for panel_x, grid in zip(panel_x_values[:2], [truth_grid, observed_grid]):
        buckets = {color: [] for color in HEIGHT_COLORS}
        for cell, z_value in grid.items():
            buckets[height_color(z_value, min_height, max_height)].append(cell)
        for color in HEIGHT_COLORS:
            path_element = grid_path(
                buckets[color],
                color,
                index_bounds,
                panel_x,
                panel_y,
                panel_width,
                panel_height,
            )
            if path_element:
                svg.append(path_element)

    truth_cells = set(truth_grid)
    observed_cells = set(observed_grid)
    categories = [
        (truth_cells - observed_cells, "#d73027"),
        (truth_cells & observed_cells, "#1a9850"),
        (observed_cells - truth_cells, "#4575b4"),
    ]
    for cells, color in categories:
        path_element = grid_path(
            cells,
            color,
            index_bounds,
            panel_x_values[2],
            panel_y,
            panel_width,
            panel_height,
        )
        if path_element:
            svg.append(path_element)

    legend_y = 660
    legend_items = [
        ("Truth only", "#d73027"),
        ("Overlap", "#1a9850"),
        ("Observed only", "#4575b4"),
    ]
    legend_x = panel_x_values[2]
    for label, color in legend_items:
        svg.append(
            '<rect x="{:.1f}" y="{}" width="22" height="22" fill="{}"/>'.format(
                legend_x, legend_y - 18, color
            )
        )
        svg.append(
            '<text class="small" x="{:.1f}" y="{}">{}</text>'.format(
                legend_x + 31, legend_y, label
            )
        )
        legend_x += 165

    runtime_seconds = runtime.get("finish_time_s")
    runtime_text = "n/a" if runtime_seconds is None else "{:.1f} s".format(runtime_seconds)
    metrics_text = (
        "Recall: {recall:.1%}   Precision: {precision:.1%}   F1: {f1:.1%}   "
        "Finish: {finish}   Path: {path:.1f} m"
    ).format(
        recall=coverage["surface_recall"],
        precision=coverage["surface_precision"],
        f1=coverage["surface_f1"],
        finish=runtime_text,
        path=runtime.get("path_length_m", 0.0),
    )
    svg.append(
        '<text class="metric" x="{}" y="730">{}</text>'.format(
            margin, svg_escape(metrics_text)
        )
    )
    svg.append(
        '<text class="small" x="{}" y="760">'
        "Visualization resolution: {:.2f} m; metric tolerance: {} voxel(s)."
        "</text>".format(
            margin, resolution, coverage["tolerance_voxels"]
        )
    )
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_summary_csv(path, variant, run_id, runtime, coverage_1, coverage_2):
    fields = [
        "run_id",
        "variant",
        "passed",
        "finish_time_s",
        "duration_s",
        "path_length_m",
        "collision_replan_logs",
        "plan_fail_logs",
        "final_map_points",
        "surface_recall_tol1",
        "surface_precision_tol1",
        "surface_f1_tol1",
        "surface_recall_tol2",
        "surface_precision_tol2",
        "surface_f1_tol2",
    ]
    row = {
        "run_id": run_id,
        "variant": variant,
        "passed": runtime.get("passed"),
        "finish_time_s": runtime.get("finish_time_s"),
        "duration_s": runtime.get("duration_s"),
        "path_length_m": runtime.get("path_length_m"),
        "collision_replan_logs": runtime.get("diagnostics", {}).get(
            "collision_replan_logs"
        ),
        "plan_fail_logs": runtime.get("diagnostics", {}).get("plan_fail_logs"),
        "final_map_points": runtime.get("outputs", {})
        .get("final_occupancy_map", {})
        .get("points"),
        "surface_recall_tol1": coverage_1["surface_recall"],
        "surface_precision_tol1": coverage_1["surface_precision"],
        "surface_f1_tol1": coverage_1["surface_f1"],
        "surface_recall_tol2": coverage_2["surface_recall"],
        "surface_precision_tol2": coverage_2["surface_precision"],
        "surface_f1_tol2": coverage_2["surface_f1"],
    }
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=sorted(VARIANT_BOUNDS), required=True)
    parser.add_argument("--runtime-json", type=Path, required=True)
    parser.add_argument("--map-pcd", type=Path, required=True)
    parser.add_argument("--truth-pcd", type=Path, required=True)
    parser.add_argument("--overlay-manifest", type=Path)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--resolution", type=float, default=0.1)
    parser.add_argument("--figure-resolution", type=float, default=0.2)
    parser.add_argument("--bounds", type=float, nargs=6)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    for required_path in (
        arguments.runtime_json,
        arguments.map_pcd,
        arguments.truth_pcd,
    ):
        if not required_path.is_file():
            raise FileNotFoundError(required_path)
    if arguments.overlay_manifest is not None and not arguments.overlay_manifest.is_file():
        raise FileNotFoundError(arguments.overlay_manifest)
    if arguments.resolution <= 0.0 or arguments.figure_resolution <= 0.0:
        raise ValueError("resolutions must be positive")

    bounds = arguments.bounds or VARIANT_BOUNDS[arguments.variant]
    run_id = arguments.run_id or datetime.now().strftime(
        "%Y%m%d_%H%M%S_{}".format(arguments.variant)
    )
    script_path = Path(__file__).resolve()
    stage_root = script_path.parents[1]
    repository_root = stage_root.parents[1]
    results_root = arguments.results_root or stage_root / "experiments" / "results"
    final_run_directory = results_root / run_id
    run_directory = results_root / (run_id + ".incomplete")
    if final_run_directory.exists() or run_directory.exists():
        raise FileExistsError(
            "result directory already exists; choose another --run-id: {}".format(
                final_run_directory
            )
        )

    runtime = json.loads(arguments.runtime_json.read_text(encoding="utf-8-sig"))
    truth_points = read_ascii_pcd(arguments.truth_pcd, bounds)
    observed_points = read_ascii_pcd(arguments.map_pcd, bounds)
    coverage_1 = evaluate(
        truth_points, observed_points, arguments.resolution, 1, bounds
    )
    coverage_2 = evaluate(
        truth_points, observed_points, arguments.resolution, 2, bounds
    )

    run_directory.mkdir(parents=True)
    copied_files = {
        "runtime": run_directory / "runtime.json",
        "map": run_directory / "final_occupancy.pcd",
        "coverage_tol1": run_directory / "surface_coverage_tol1.json",
        "coverage_tol2": run_directory / "surface_coverage_tol2.json",
    }
    shutil.copy2(arguments.runtime_json, copied_files["runtime"])
    shutil.copy2(arguments.map_pcd, copied_files["map"])
    copied_files["coverage_tol1"].write_text(
        json.dumps(coverage_1, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    copied_files["coverage_tol2"].write_text(
        json.dumps(coverage_2, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if arguments.overlay_manifest is not None:
        copied_files["overlay_manifest"] = run_directory / "overlay_manifest.json"
        shutil.copy2(arguments.overlay_manifest, copied_files["overlay_manifest"])

    write_summary_csv(
        run_directory / "summary.csv",
        arguments.variant,
        run_id,
        runtime,
        coverage_1,
        coverage_2,
    )
    write_topdown_svg(
        run_directory / "figure_reconstruction_topdown.svg",
        truth_points,
        observed_points,
        bounds,
        arguments.figure_resolution,
        runtime,
        coverage_1,
    )

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_local_time": datetime.now().astimezone().isoformat(),
        "variant": arguments.variant,
        "evaluation_bounds_m": bounds,
        "metric_resolution_m": arguments.resolution,
        "figure_resolution_m": arguments.figure_resolution,
        "paper_repository_commit": git_commit(repository_root),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "inputs": {
            "truth_pcd": str(arguments.truth_pcd.resolve()),
            "truth_pcd_sha256": sha256(arguments.truth_pcd),
            "runtime_json": str(arguments.runtime_json.resolve()),
            "map_pcd": str(arguments.map_pcd.resolve()),
            "overlay_manifest": (
                None
                if arguments.overlay_manifest is None
                else str(arguments.overlay_manifest.resolve())
            ),
        },
        "artifacts": {
            path.name: {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(run_directory.iterdir())
            if path.is_file()
        },
        "scientific_boundary": {
            "truth_read_after_exploration_only": True,
            "predefined_route_used": False,
            "predefined_waypoints_used": False,
            "manual_region_partition_used": False,
        },
    }
    (run_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_directory / "notes.md").write_text(
        "# Trial Notes\n\n"
        "- Run ID: `{}`\n"
        "- Variant: `{}`\n"
        "- Runtime pass: `{}`\n"
        "- FUEL finish time: `{}` s\n"
        "- Path length: `{}` m\n"
        "- Surface recall (0.1 m, tolerance 1): `{:.2%}`\n"
        "- Surface recall (0.1 m, tolerance 2): `{:.2%}`\n\n"
        "Add observations about abnormal behavior, VM load, and any manual "
        "intervention. Do not edit machine-generated JSON or CSV files.\n".format(
            run_id,
            arguments.variant,
            runtime.get("passed"),
            runtime.get("finish_time_s"),
            runtime.get("path_length_m"),
            coverage_1["surface_recall"],
            coverage_2["surface_recall"],
        ),
        encoding="utf-8",
    )

    run_directory.rename(final_run_directory)
    print("Paper trial archived: {}".format(final_run_directory))
    print(
        "Figure: {}".format(
            final_run_directory / "figure_reconstruction_topdown.svg"
        )
    )
    print("Summary: {}".format(final_run_directory / "summary.csv"))


if __name__ == "__main__":
    main()
