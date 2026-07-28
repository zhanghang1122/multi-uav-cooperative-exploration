#!/usr/bin/env python3
"""Create an auditable, non-tuned diagnosis for one FUEL baseline trial.

This tool deliberately does not decide that FUEL is good or bad from one map.
It checks whether a run is complete enough to enter the calibration dataset and
summarises evidence that must be reviewed before the baseline decision gate.
"""

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_DIRECTORY / "validate_paper_run.py"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def summarize_coverage(rows):
    valid = [
        row for row in rows
        if number(row.get("elapsed_s")) is not None
        and number(row.get("surface_recall")) is not None
    ]
    if not valid:
        return {"samples": 0}
    final = valid[-1]
    end_time = number(final["elapsed_s"])
    window_start = max(0.0, end_time - max(60.0, end_time * 0.2))
    early = next(
        (row for row in valid if number(row["elapsed_s"]) >= window_start),
        valid[0],
    )
    recalls = [number(row["surface_recall"]) for row in valid]
    auc = 0.0
    for left, right in zip(valid, valid[1:]):
        left_time = number(left["elapsed_s"])
        right_time = number(right["elapsed_s"])
        auc += (right_time - left_time) * (
            number(left["surface_recall"]) + number(right["surface_recall"])
        ) / 2.0
    return {
        "samples": len(valid),
        "final_time_s": round(end_time, 3),
        "final_surface_recall": round(number(final["surface_recall"]), 6),
        "final_surface_precision": round(number(final.get("surface_precision")) or 0.0, 6),
        "final_surface_f1": round(number(final.get("surface_f1")) or 0.0, 6),
        "coverage_auc_recall_seconds": round(auc, 6),
        "last_window_start_s": round(number(early["elapsed_s"]), 3),
        "last_window_recall_gain": round(
            number(final["surface_recall"]) - number(early["surface_recall"]), 6
        ),
        "maximum_surface_recall": round(max(recalls), 6),
    }


def summarize_timing(rows):
    timings = [number(row.get("duration_s")) for row in rows]
    timings = [value for value in timings if value is not None and value >= 0.0]
    modules = Counter(row.get("module", "unknown") for row in rows)
    if not timings:
        return {"samples": 0, "modules": dict(modules)}
    return {
        "samples": len(timings),
        "modules": dict(sorted(modules.items())),
        "mean_s": round(statistics.mean(timings), 6),
        "p95_s": round(percentile(timings, 0.95), 6),
        "max_s": round(max(timings), 6),
    }


def summarize_resources(rows):
    rtfs = [number(row.get("realtime_factor")) for row in rows]
    rtfs = [value for value in rtfs if value is not None and value >= 0.0]
    rss = [number(row.get("ros_process_rss_mb")) for row in rows]
    rss = [value for value in rss if value is not None and value >= 0.0]
    if not rtfs and not rss:
        return {"samples": 0}
    return {
        "samples": len(rows),
        "mean_realtime_factor": None if not rtfs else round(statistics.mean(rtfs), 4),
        "minimum_realtime_factor": None if not rtfs else round(min(rtfs), 4),
        "peak_ros_process_rss_mb": None if not rss else round(max(rss), 3),
    }


def event_counts(path):
    counts = Counter()
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            counts[str(record.get("event", "unknown"))] += 1
    return dict(sorted(counts.items()))


def validate_artifacts(run_directory):
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--allow-debug", str(run_directory)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {
            "passed": False,
            "errors": ["artifact validator did not return JSON", completed.stderr.strip()],
        }
    return payload


def classify(artifacts, runtime, manifest, coverage):
    if not artifacts.get("passed"):
        return "instrumentation_incomplete", [
            "Do not interpret mapping quality. Repair missing or malformed evidence first."
        ]
    if runtime.get("passed") is not True:
        return "execution_incomplete", [
            "Retain this run as a failure record and diagnose launch, sensing, planning, or timeout causes."
        ]
    if manifest.get("run_class") != "formal":
        return "debug_or_calibration_only", [
            "The run is technically complete, but it is not a formal paper sample.",
            "Use it to freeze bounds, sensor settings, timeout, and evaluation definitions before P1."
        ]
    recommendations = [
        "This run can enter the formal dataset only after paired repetitions and the frozen protocol review.",
        "Interpret all-surface recall with an observability audit; occluded or inaccessible surfaces must not be treated as planner failures by default."
    ]
    if coverage.get("last_window_recall_gain", 0.0) > 0.0:
        recommendations.append(
            "Coverage was still increasing near termination. Inspect FUEL finish criteria and the exploration bounds before comparing methods."
        )
    return "formal_sample_pending_repeatability", recommendations


def render_markdown(payload):
    verdict = payload["verdict"]
    coverage = payload["coverage"]
    lines = [
        "# FUEL Baseline Diagnosis",
        "",
        "## Decision Status",
        "",
        "- Classification: `{}`".format(verdict["classification"]),
        "- Trial directory: `{}`".format(payload["run_directory"]),
        "- Runtime passed: `{}`".format(payload["runtime_passed"]),
        "- Run class: `{}`".format(payload["run_class"]),
        "",
        "This report does **not** label FUEL as good or bad. A single trial cannot separate algorithmic limitations from sensor visibility, reachable-space definition, map integration, parameterisation, or virtual-machine timing.",
        "",
        "## Observed Evidence",
        "",
        "- Final occupied-surface recall: `{}`".format(coverage.get("final_surface_recall")),
        "- Final occupied-surface precision: `{}`".format(coverage.get("final_surface_precision")),
        "- Final occupied-surface F1: `{}`".format(coverage.get("final_surface_f1")),
        "- Recall gain in final analysis window: `{}`".format(coverage.get("last_window_recall_gain")),
        "- Path length (m): `{}`".format(payload["runtime"].get("path_length_m")),
        "- Finish time (s): `{}`".format(payload["runtime"].get("finish_time_s")),
        "",
        "## Required Interpretation",
        "",
    ]
    lines.extend("- {}".format(item) for item in verdict["recommendations"])
    lines.extend([
        "",
        "## Before Replacing FUEL",
        "",
        "1. Complete P0 on the upstream FUEL office example and Ruins base with the same recorder.",
        "2. Audit reachable/observable truth separately from the full simulator surface cloud.",
        "3. Run three calibration repeats on base, medium, and complex with frozen bounds and sensors.",
        "4. Compare completion, coverage curve, path length, planning latency, and real-time factor across repeats.",
        "5. Replace FUEL only if controlled evidence shows it cannot provide a stable, reproducible single-UAV baseline. Preserve all failed runs either way.",
        "",
    ])
    return "\n".join(lines)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    run_directory = arguments.run_directory.resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError(run_directory)

    artifacts = validate_artifacts(run_directory)
    runtime = read_json(run_directory / "runtime.json")
    manifest = read_json(run_directory / "run_manifest.yaml")
    coverage = summarize_coverage(read_csv(run_directory / "coverage_timeseries.csv"))
    timing = summarize_timing(read_csv(run_directory / "planning_timing.csv"))
    resources = summarize_resources(read_csv(run_directory / "system_resources.csv"))
    classification, recommendations = classify(artifacts, runtime, manifest, coverage)
    payload = {
        "schema_version": 1,
        "run_directory": str(run_directory),
        "artifact_validation": artifacts,
        "runtime": {
            "passed": runtime.get("passed"),
            "finish_time_s": runtime.get("finish_time_s"),
            "path_length_m": runtime.get("path_length_m"),
            "diagnostics": runtime.get("diagnostics", {}),
        },
        "runtime_passed": runtime.get("passed") is True,
        "run_class": manifest.get("run_class"),
        "coverage": coverage,
        "planning_timing": timing,
        "resources": resources,
        "events": event_counts(run_directory / "events.jsonl"),
        "verdict": {
            "classification": classification,
            "recommendations": recommendations,
            "algorithm_judgement": "not_determined_from_one_trial",
        },
    }
    output_json = arguments.output_json or run_directory / "baseline_diagnosis.json"
    output_markdown = arguments.output_markdown or run_directory / "baseline_diagnosis.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
