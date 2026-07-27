#!/usr/bin/env python3

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "finalize_paper_trial.py"


def load_script():
    spec = importlib.util.spec_from_file_location("finalize_paper_trial", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


class FinalizePaperTrialTest(unittest.TestCase):
    def test_metric_and_svg_are_deterministic(self):
        module = load_script()
        truth_points = [(0.0, 0.0, 0.5), (0.2, 0.0, 1.0)]
        observed_points = [(0.0, 0.0, 0.5)]
        bounds = [-1.0, -1.0, 0.0, 1.0, 1.0, 2.0]

        coverage = module.evaluate(
            truth_points,
            observed_points,
            0.1,
            0,
            bounds,
        )

        self.assertEqual(coverage["truth_voxels"], 2)
        self.assertEqual(coverage["matched_truth_voxels"], 1)
        self.assertEqual(coverage["surface_recall"], 0.5)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "figure.svg"
            module.write_topdown_svg(
                output,
                truth_points,
                observed_points,
                bounds,
                0.2,
                {"finish_time_s": 10.0, "path_length_m": 5.0},
                coverage,
            )
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("Single-UAV 3D Mapping Result", rendered)
            self.assertIn("Simulator truth", rendered)
            self.assertIn("Online reconstruction", rendered)
            self.assertIn("Recall: 50.0%", rendered)
            self.assertIn("display z-range: 0.00-2.00 m", rendered)

    def test_read_pcd_applies_bounds(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "map.pcd"
            write_pcd(path, [(0.0, 0.0, 0.5), (3.0, 0.0, 0.5)])
            points = module.read_ascii_pcd(
                path, [-1.0, -1.0, 0.0, 1.0, 1.0, 1.0]
            )
            self.assertEqual(points, [(0.0, 0.0, 0.5)])


if __name__ == "__main__":
    unittest.main()
