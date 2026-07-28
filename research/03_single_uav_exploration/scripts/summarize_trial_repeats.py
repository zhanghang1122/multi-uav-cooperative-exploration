#!/usr/bin/env python3
"""Summarize repeated autonomous-exploration trials without selecting a best run."""

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def final_coverage(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("coverage_timeseries.csv has no rows: {}".format(path))
    return rows[-1]


def final_static_coverage(path):
    metric = read_json(path / "surface_coverage_tol1.json")
    required = ("surface_recall", "surface_precision", "surface_f1")
    if not all(key in metric for key in required):
        raise ValueError("static coverage is incomplete: {}".format(path))
    return metric


def summarize(values):
    mean = statistics.mean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "mean": round(mean, 6),
        "standard_deviation": round(standard_deviation, 6),
        "minimum": round(min(values), 6),
        "maximum": round(max(values), 6),
        "coefficient_of_variation_percent": (
            None if mean == 0.0 else round(100.0 * standard_deviation / mean, 4)
        ),
    }


def load_trial(path):
    runtime = read_json(path / "runtime.json")
    cumulative_coverage = final_coverage(path / "coverage_timeseries.csv")
    static_coverage = final_static_coverage(path)
    manifest = read_json(path / "run_manifest.yaml")
    return {
        "run_id": path.name,
        "run_class": manifest.get("run_class"),
        "runtime_passed": runtime.get("passed") is True,
        "finish_time_s": float(runtime["finish_time_s"]),
        "path_length_m": float(runtime["path_length_m"]),
        "static_surface_recall": float(static_coverage["surface_recall"]),
        "static_surface_precision": float(static_coverage["surface_precision"]),
        "static_surface_f1": float(static_coverage["surface_f1"]),
        "cumulative_observation_recall": float(cumulative_coverage["surface_recall"]),
    }


def render_markdown(payload):
    lines = [
        "# Repeated Trial Summary",
        "",
        "All listed runs are retained. This report does not select the best run.",
        "",
        "| Run | Completed | Time (s) | Path (m) | Static Recall | Static Precision | Static F1 | Cumulative Recall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["trials"]:
        lines.append(
            "| {run_id} | {runtime_passed} | {finish_time_s:.3f} | {path_length_m:.3f} | {static_surface_recall:.6f} | {static_surface_precision:.6f} | {static_surface_f1:.6f} | {cumulative_observation_recall:.6f} |".format(**row)
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        "| Metric | Mean | SD | Min | Max | CV (%) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for key, value in payload["aggregate"].items():
        lines.append(
            "| {} | {:.6f} | {:.6f} | {:.6f} | {:.6f} | {} |".format(
                key,
                value["mean"],
                value["standard_deviation"],
                value["minimum"],
                value["maximum"],
                "N/A" if value["coefficient_of_variation_percent"] is None else "{:.4f}".format(value["coefficient_of_variation_percent"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directories", nargs="+", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    trials = [load_trial(path.resolve()) for path in arguments.run_directories]
    metrics = (
        "finish_time_s",
        "path_length_m",
        "static_surface_recall",
        "static_surface_precision",
        "static_surface_f1",
        "cumulative_observation_recall",
    )
    payload = {
        "schema_version": 1,
        "trial_count": len(trials),
        "trials": trials,
        "aggregate": {key: summarize([row[key] for row in trials]) for key in metrics},
        "selection_policy": "no_best_run_selected",
    }
    output_json = arguments.output_json or Path("repeat_summary.json")
    output_markdown = arguments.output_markdown or Path("repeat_summary.md")
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_markdown.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
