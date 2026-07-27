#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "evaluate_surface_coverage.py"


def load_script():
    spec = importlib.util.spec_from_file_location("surface_coverage", SCRIPT_PATH)
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
        f"WIDTH {len(points)}",
        "HEIGHT 1",
        "VIEWPOINT 0 0 0 1 0 0 0",
        f"POINTS {len(points)}",
        "DATA ascii",
    ]
    lines.extend("{} {} {}".format(*point) for point in points)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


class SurfaceCoverageTest(unittest.TestCase):
    def test_exact_match_has_unit_scores(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth = root / "truth.pcd"
            observed = root / "observed.pcd"
            points = [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)]
            write_pcd(truth, points)
            write_pcd(observed, points)

            result = module.evaluate(truth, observed, 0.1, 0)

            self.assertEqual(result["surface_recall"], 1.0)
            self.assertEqual(result["surface_precision"], 1.0)
            self.assertEqual(result["surface_f1"], 1.0)

    def test_one_voxel_tolerance_matches_quantization_shift(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth = root / "truth.pcd"
            observed = root / "observed.pcd"
            write_pcd(truth, [(0.0, 0.0, 0.0)])
            write_pcd(observed, [(0.1, 0.0, 0.0)])

            result = module.evaluate(truth, observed, 0.1, 1)

            self.assertEqual(result["surface_recall"], 1.0)
            self.assertEqual(result["surface_precision"], 1.0)

    def test_bounds_exclude_points_outside_the_experiment_volume(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth = root / "truth.pcd"
            observed = root / "observed.pcd"
            write_pcd(truth, [(0.0, 0.0, 0.0), (0.0, 0.0, 3.0)])
            write_pcd(observed, [(0.0, 0.0, 0.0)])

            result = module.evaluate(
                truth,
                observed,
                0.1,
                0,
                [-1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
            )

            self.assertEqual(result["surface_recall"], 1.0)
            self.assertEqual(result["truth_voxels"], 1)


if __name__ == "__main__":
    unittest.main()
