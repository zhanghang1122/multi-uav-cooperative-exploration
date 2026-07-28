#!/usr/bin/env python3
"""Test ROS-independent formatting used by the runtime interface probe."""

import importlib.util
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "fuel_mapping_interface_probe.py"


def load_script():
    spec = importlib.util.spec_from_file_location("fuel_mapping_interface_probe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Header:
    class Stamp:
        secs = 12
        nsecs = 34

    frame_id = "/sensor"
    stamp = Stamp()


class Field:
    def __init__(self, name):
        self.name = name


class Cloud:
    header = Header()
    width = 4
    height = 2
    fields = [Field("x"), Field("y"), Field("z")]


class Image:
    header = Header()


class ProbeFormattingTest(unittest.TestCase):
    def test_cloud_summary_normalizes_frame_and_count(self):
        module = load_script()
        summary = module.message_summary(Cloud(), "sensor_msgs/PointCloud2")
        self.assertEqual(summary["frame_id"], "sensor")
        self.assertEqual(summary["points"], 8)
        self.assertEqual(summary["fields"], ["x", "y", "z"])
        self.assertEqual(summary["stamp"], {"secs": 12, "nsecs": 34})

    def test_image_summary_has_frame_without_point_cloud_fields(self):
        module = load_script()
        summary = module.message_summary(Image(), "sensor_msgs/Image")
        self.assertEqual(summary["frame_id"], "sensor")
        self.assertNotIn("points", summary)


if __name__ == "__main__":
    unittest.main()
