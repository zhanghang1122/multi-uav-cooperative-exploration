#!/usr/bin/env python3
"""Test the read-only FUEL launch interface inspector."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "inspect_fuel_overlay.py"


def load_script():
    spec = importlib.util.spec_from_file_location("inspect_fuel_overlay", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InspectFuelOverlayTest(unittest.TestCase):
    def test_records_declared_nodes_and_remaps(self):
        module = load_script()
        launch = """<launch>
  <include file=\"$(find other)/launch/sensor.xml\"><arg name=\"rate\" value=\"10\"/></include>
  <node pkg=\"local_sensing\" type=\"pcl_render_node\" name=\"renderer\" output=\"screen\">
    <remap from=\"cloud\" to=\"/lidar/cloud\"/>
  </node>
</launch>"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.launch"
            path.write_text(launch, encoding="utf-8")
            interfaces = module.parse_xml_interfaces(path)
        self.assertEqual(len(interfaces["nodes"]), 1)
        self.assertEqual(interfaces["nodes"][0]["package"], "local_sensing")
        self.assertEqual(
            interfaces["nodes"][0]["remaps"],
            [{"from": "cloud", "to": "/lidar/cloud"}],
        )
        self.assertEqual(interfaces["includes"][0]["arguments"][0]["name"], "rate")


if __name__ == "__main__":
    unittest.main()
