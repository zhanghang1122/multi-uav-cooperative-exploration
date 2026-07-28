#!/usr/bin/env python3
"""Reject incomplete runs before they enter the paper dataset."""

import argparse
import csv
import json
from pathlib import Path


REQUIRED_FILES = (
    "run_manifest.yaml",
    "runtime.json",
    "trajectory.csv",
    "occupancy_first_seen.csv",
    "map_growth_timeseries.csv",
    "coverage_timeseries.csv",
    "planning_timing.csv",
    "system_resources.csv",
    "events.jsonl",
    "planner_rosout.jsonl",
    "final_occupancy.pcd",
    "software_versions.txt",
    "notes.md",
)

CSV_COLUMNS = {
    "trajectory.csv": {"elapsed_s", "x_m", "y_m", "z_m"},
    "occupancy_first_seen.csv": {
        "voxel_x",
        "voxel_y",
        "voxel_z",
        "first_seen_s",
    },
    "map_growth_timeseries.csv": {
        "elapsed_s",
        "occupied_voxels",
        "new_voxels",
    },
    "coverage_timeseries.csv": {
        "elapsed_s",
        "surface_recall",
        "surface_precision",
        "surface_f1",
    },
    "planning_timing.csv": {"elapsed_s", "module", "duration_s"},
    "system_resources.csv": {
        "elapsed_wall_s",
        "realtime_factor",
        "system_cpu_percent",
        "memory_available_mb",
        "ros_process_rss_mb",
    },
}


def validate_json_lines(path):
    count = 0
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "{} line {} is invalid JSON: {}".format(
                        path.name, line_number, error
                    )
                )
            count += 1
    if count == 0:
        raise ValueError("{} contains no records".format(path.name))


def validate_csv(path, required_columns):
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = required_columns.difference(columns)
        if missing:
            raise ValueError(
                "{} is missing columns: {}".format(
                    path.name, ", ".join(sorted(missing))
                )
            )
        if next(reader, None) is None:
            raise ValueError("{} contains no data rows".format(path.name))


def validate_run(run_directory, require_formal=True):
    errors = []
    for filename in REQUIRED_FILES:
        path = run_directory / filename
        if not path.is_file():
            errors.append("missing {}".format(filename))
        elif path.stat().st_size == 0:
            errors.append("empty {}".format(filename))

    if errors:
        return errors

    try:
        run_manifest = json.loads(
            (run_directory / "run_manifest.yaml").read_text(encoding="utf-8")
        )
        if require_formal and run_manifest.get("run_class") != "formal":
            errors.append("run_class is not formal")
        if run_manifest.get("prior_route_allowed") is not False:
            errors.append("manifest does not prohibit prior routes")
        if run_manifest.get("truth_map_usage") != "offline_evaluation_only":
            errors.append("truth-map boundary is not auditable")
    except (json.JSONDecodeError, OSError) as error:
        errors.append("invalid run_manifest.yaml: {}".format(error))

    try:
        runtime = json.loads(
            (run_directory / "runtime.json").read_text(encoding="utf-8-sig")
        )
        if require_formal and runtime.get("passed") is not True:
            errors.append("runtime validation did not pass")
    except (json.JSONDecodeError, OSError) as error:
        errors.append("invalid runtime.json: {}".format(error))

    for filename, columns in CSV_COLUMNS.items():
        try:
            validate_csv(run_directory / filename, columns)
        except (ValueError, OSError) as error:
            errors.append(str(error))
    for filename in ("events.jsonl", "planner_rosout.jsonl"):
        try:
            validate_json_lines(run_directory / filename)
        except (ValueError, OSError) as error:
            errors.append(str(error))
    return errors


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument(
        "--allow-debug",
        action="store_true",
        help="Check artifact completeness without requiring run_class=formal.",
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    if not arguments.run_directory.is_dir():
        raise FileNotFoundError(arguments.run_directory)
    errors = validate_run(
        arguments.run_directory,
        require_formal=not arguments.allow_debug,
    )
    payload = {
        "schema_version": 1,
        "run_directory": str(arguments.run_directory.resolve()),
        "formal_required": not arguments.allow_debug,
        "passed": not errors,
        "errors": errors,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(rendered + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
