#!/usr/bin/env python3
"""Unit tests for the non-destructive FUEL overlay generator."""

import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = STAGE_ROOT.parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "prepare_fuel_overlay.py"


def load_script():
    spec = importlib.util.spec_from_file_location("prepare_fuel_overlay", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPLORATION = """<launch>
<arg name=\"map_size_x\" value=\"50.0\"/><arg name=\"map_size_y\" value=\"50.0\"/><arg name=\"map_size_z\" value=\"10.0\"/>
<arg name=\"init_x\" value=\"0.0\"/><arg name=\"init_y\" value=\"0.0\"/><arg name=\"init_z\" value=\"1.0\"/>
<include file=\"$(find exploration_manager)/launch/algorithm.xml\"/><include file=\"$(find exploration_manager)/launch/simulator.xml\"/>
</launch>"""
SIMULATOR = """<launch><node pkg=\"map_generator\" name=\"map_pub\" type=\"map_pub\" args=\"office.pcd\"/></launch>"""


class OverlayTest(unittest.TestCase):
    def test_generates_overlay_without_editing_upstream(self):
        module = load_script()
        self.assertNotIn("ET.indent(", SCRIPT_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launch = root / "fuel_ws/src/FUEL/fuel_planner/exploration_manager/launch"
            launch.mkdir(parents=True)
            (launch / "exploration.launch").write_text(EXPLORATION, encoding="utf-8")
            (launch / "simulator.xml").write_text(SIMULATOR, encoding="utf-8")
            (launch / "algorithm.xml").write_text("<launch/>", encoding="utf-8")
            before = (launch / "exploration.launch").read_bytes()
            pcd = REPOSITORY_ROOT / "research/01_ruins_environment/maps/pcd/Ruins-Urban-01_base.pcd"
            generated, manifest_path = module.generate_overlay(root / "fuel_ws", pcd, root / "output", "base")
            root_xml = ET.parse(generated).getroot()
            self.assertEqual(module.direct_arg(root_xml, "init_x").get("value"), "-19.2")
            self.assertEqual((launch / "exploration.launch").read_bytes(), before)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["scientific_boundary"]["planner_prior_map"])
            self.assertFalse(manifest["scientific_boundary"]["planner_predefined_waypoints"])

    def test_variant_specific_height_bounds(self):
        module = load_script()
        self.assertEqual(module.exploration_box("base")["box_max_z"], "2.65")
        self.assertEqual(module.exploration_box("complex")["box_max_z"], "5.00")


if __name__ == "__main__":
    unittest.main()
