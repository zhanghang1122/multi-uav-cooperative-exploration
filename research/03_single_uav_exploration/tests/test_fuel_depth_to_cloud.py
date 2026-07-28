#!/usr/bin/env python3
"""Test the ROS-independent depth decoding and projection functions."""

import importlib.util
import struct
import unittest
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "fuel_depth_to_cloud.py"


def load_script():
    spec = importlib.util.spec_from_file_location("fuel_depth_to_cloud", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DepthMessage:
    encoding = "32FC1"
    is_bigendian = False
    width = 2
    height = 2
    step = 8
    data = struct.pack("<ffff", 1.0, 2.0, 0.0, float("nan"))


class FuelDepthProjectionTest(unittest.TestCase):
    def test_decodes_float_depth_and_projects_only_valid_pixels(self):
        module = load_script()
        depth = module.image_to_depth(DepthMessage(), 1000.0)
        self.assertEqual(depth[:1], [[1.0, 2.0]])
        points = module.project_depth(depth, 1.0, 1.0, 0.0, 0.0, 1, 0.2, 5.0)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0], (0.0, 0.0, 1.0))
        self.assertEqual(points[1], (2.0, 0.0, 2.0))


if __name__ == "__main__":
    unittest.main()
