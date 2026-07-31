#!/usr/bin/env python3
"""Summarize completed B1 trial JSON files without changing experiment data."""

from __future__ import print_function

import argparse
import csv
import json
import math
import os
import sys


METRICS = (
    ("precision", "surface_precision", "higher"),
    ("recall", "surface_recall", "higher"),
    ("f1", "surface_f1", "higher"),
    ("T80", "T80_s", "lower"),
    ("T90", "T90_s", "lower"),
    ("T95", "T95_s", "lower"),
    ("duration_s", "mission_duration_s", "lower"),
    ("path_length_m", "path_length_m", "lower"),
    ("planner_messages", "planner_messages", "diagnostic"),
)


def mean(values):
    return sum(values) / float(len(values))


def sample_std(values):
    if len(values) < 2:
        return 0.0
    average = mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def read_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def read_trial(run_dir):
    trial_path = os.path.join(run_dir, "trial_summary.json")
    quality_path = os.path.join(run_dir, "map_quality.json")
    if not os.path.isfile(trial_path) or not os.path.isfile(quality_path):
        raise RuntimeError("missing trial_summary.json or map_quality.json: " + run_dir)
    trial = read_json(trial_path)
    quality = read_json(quality_path)
    if not trial.get("success", False):
        raise RuntimeError("trial is not successful: " + run_dir)
    if trial.get("runtime_contract", {}).get("truth_map_usage") != "offline_evaluation_only":
        raise RuntimeError("truth-map runtime contract is invalid: " + run_dir)
    coverage = quality.get("coverage_time_metrics", {}).get("time_to_surface_recall_s", {})
    return {
        "run_dir": os.path.abspath(run_dir),
        "precision": quality["precision"],
        "recall": quality["recall"],
        "f1": quality["f1"],
        "T80": coverage.get("T80"),
        "T90": coverage.get("T90"),
        "T95": coverage.get("T95"),
        "duration_s": trial["duration_s"],
        "path_length_m": trial["path_length_m"],
        "planner_messages": trial["planner_messages"],
        "scene": trial["scene"],
        "method_id": trial["method_id"],
    }


def summarize(records):
    summary = {}
    for field, label, direction in METRICS:
        values = [record[field] for record in records if record[field] is not None]
        summary[label] = {
            "direction": direction,
            "reached_trials": len(values),
            "not_reached_trials": len(records) - len(values),
            "mean": None if not values else mean(values),
            "sample_std": None if not values else sample_std(values),
            "min": None if not values else min(values),
            "max": None if not values else max(values),
        }
    return summary


def write_csv(path, records):
    fields = ["run_dir", "precision", "recall", "f1", "T80", "T90", "T95",
              "duration_s", "path_length_m", "planner_messages"]
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record[field] for field in fields})


def main():
    parser = argparse.ArgumentParser(
        description="Summarize completed B1 trials for a paper table. Read-only.")
    parser.add_argument("run_dirs", nargs="+", help="directories containing B1 result JSON files")
    parser.add_argument("--output", required=True, help="summary JSON output path")
    parser.add_argument("--per-trial-csv", help="optional CSV table for individual trial values")
    args = parser.parse_args()

    records = [read_trial(path) for path in args.run_dirs]
    scenes = sorted(set(record["scene"] for record in records))
    methods = sorted(set(record["method_id"] for record in records))
    if len(scenes) != 1 or len(methods) != 1:
        raise RuntimeError("all trials must use one scene and one method")

    output = {
        "schema_version": 1,
        "analysis_mode": "offline_read_only_summary",
        "method_id": methods[0],
        "scene": scenes[0],
        "trials": len(records),
        "reporting": "mean_plus_minus_sample_standard_deviation",
        "records": records,
        "metrics": summarize(records),
        "notes": [
            "T80/T90/T95 are reported only across trials that reached that threshold.",
            "A null T value means the FUEL baseline terminated before reaching that declared coverage threshold.",
            "Ground-truth PCD is used only by the already completed offline evaluator.",
        ],
    }
    output_parent = os.path.dirname(os.path.abspath(args.output))
    if output_parent and not os.path.isdir(output_parent):
        os.makedirs(output_parent)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if args.per_trial_csv:
        csv_parent = os.path.dirname(os.path.abspath(args.per_trial_csv))
        if csv_parent and not os.path.isdir(csv_parent):
            os.makedirs(csv_parent)
        write_csv(args.per_trial_csv, records)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print("B1 summary failed: {}".format(error), file=sys.stderr)
        sys.exit(2)
