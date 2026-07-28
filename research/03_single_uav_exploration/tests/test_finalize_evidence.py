#!/usr/bin/env python3

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
FINALIZER = STAGE_ROOT / "scripts" / "finalize_paper_trial.py"
VALIDATOR = STAGE_ROOT / "scripts" / "validate_paper_run.py"


def write_pcd(path, points):
    lines = [
        "VERSION 0.7",
        "FIELDS x y z",
        "SIZE 4 4 4",
        "TYPE F F F",
        "COUNT 1 1 1",
        "WIDTH {}".format(len(points)),
        "HEIGHT 1",
        "VIEWPOINT 0 0 0 1 0 0 0",
        "POINTS {}".format(len(points)),
        "DATA ascii",
    ]
    lines.extend("{} {} {}".format(*point) for point in points)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def write_csv(path, columns):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow({column: "1" for column in columns})


class FinalizeEvidenceTest(unittest.TestCase):
    def test_finalizer_archives_evidence_and_builds_progress_curve(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth = root / "truth.pcd"
            observed = root / "observed.pcd"
            runtime = root / "runtime.json"
            evidence = root / "evidence"
            results = root / "results"
            evidence.mkdir()
            write_pcd(truth, [(0.0, 0.0, 0.5), (0.2, 0.0, 0.5)])
            write_pcd(observed, [(0.0, 0.0, 0.5)])
            runtime.write_text(
                json.dumps(
                    {"passed": True, "finish_time_s": 2.0, "path_length_m": 1.0}
                ),
                encoding="utf-8",
            )
            (evidence / "run_manifest.yaml").write_text(
                json.dumps(
                    {
                        "run_class": "formal",
                        "prior_route_allowed": False,
                        "truth_map_usage": "offline_evaluation_only",
                    }
                ),
                encoding="utf-8",
            )
            with (evidence / "occupancy_first_seen.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(("voxel_x", "voxel_y", "voxel_z", "first_seen_s"))
                writer.writerow((0, 0, 5, 1.0))
            write_csv(
                evidence / "trajectory.csv",
                ("elapsed_s", "x_m", "y_m", "z_m"),
            )
            write_csv(
                evidence / "map_growth_timeseries.csv",
                ("elapsed_s", "occupied_voxels", "new_voxels"),
            )
            write_csv(
                evidence / "planning_timing.csv",
                ("elapsed_s", "module", "duration_s"),
            )
            write_csv(
                evidence / "system_resources.csv",
                (
                    "elapsed_wall_s",
                    "realtime_factor",
                    "system_cpu_percent",
                    "memory_available_mb",
                    "ros_process_rss_mb",
                ),
            )
            for filename in ("events.jsonl", "planner_rosout.jsonl"):
                (evidence / filename).write_text('{"event":"test"}\n', encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(FINALIZER),
                    "--variant",
                    "base",
                    "--runtime-json",
                    str(runtime),
                    "--map-pcd",
                    str(observed),
                    "--truth-pcd",
                    str(truth),
                    "--evidence-dir",
                    str(evidence),
                    "--results-root",
                    str(results),
                    "--run-id",
                    "formal_fixture",
                    "--bounds",
                    "-1",
                    "-1",
                    "0",
                    "1",
                    "1",
                    "1",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            run_directory = results / "formal_fixture"
            self.assertTrue((run_directory / "coverage_timeseries.csv").is_file())
            self.assertTrue((run_directory / "software_versions.txt").is_file())
            validation = subprocess.run(
                [sys.executable, str(VALIDATOR), str(run_directory)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)


if __name__ == "__main__":
    unittest.main()
