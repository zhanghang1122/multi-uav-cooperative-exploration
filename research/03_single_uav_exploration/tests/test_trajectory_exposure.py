#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "evaluate_trajectory_exposure.py"


def load_script():
    spec = importlib.util.spec_from_file_location("trajectory_exposure", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrajectoryExposureTest(unittest.TestCase):
    def test_nearby_truth_is_exposed_but_distant_truth_is_not(self):
        module = load_script()
        truth = {(0, 0, 0), (30, 0, 0)}
        exposed = module.exposed_truth_voxels(
            truth, [(0.0, 0.0, 0.0)], resolution=0.1, sensor_range_m=1.0
        )
        self.assertEqual(exposed, {(0, 0, 0)})

    def test_wall_voxel_blocks_line_of_sight_to_farther_surface(self):
        module = load_script()
        occupied = {(3, 0, 0), (5, 0, 0)}
        self.assertFalse(
            module.line_of_sight_clear((0, 0, 0), (5, 0, 0), occupied)
        )
        self.assertTrue(
            module.line_of_sight_clear((0, 0, 0), (3, 0, 0), occupied)
        )


if __name__ == "__main__":
    unittest.main()
