#!/usr/bin/env python3
"""Unit test the non-destructive FUEL launch overlay generator."""

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


EXPLORATION_XML = """\
<launch>
  <arg name="map_size_x" value="50.0"/>
  <arg name="map_size_y" value="50.0"/>
  <arg name="map_size_z" value="10.0"/>
  <arg name="init_x" value="0.0"/>
  <arg name="init_y" value="0.0"/>
  <arg name="init_z" value="1.0"/>
  <include file="$(find exploration_manager)/launch/algorithm.xml">
    <arg name="box_min_x" value="-10.0"/>
    <arg name="box_min_y" value="-10.0"/>
    <arg name="box_min_z" value="0.0"/>
    <arg name="box_max_x" value="10.0"/>
    <arg name="box_max_y" value="10.0"/>
    <arg name="box_max_z" value="2.0"/>
  </include>
  <include file="$(find exploration_manager)/launch/simulator.xml"/>
</launch>
"""

SIMULATOR_XML = """\
<launch>
  <arg name="box_min_x"/>
  <arg name="box_min_y"/>
  <arg name="box_min_z"/>
  <arg name="box_max_x"/>
  <arg name="box_max_y"/>
  <arg name="box_max_z"/>
  <node pkg="map_generator" name="map_pub" type="map_pub"
        args="$(find map_generator)/resource/office.pcd"/>
</launch>
"""


class OverlayTest(unittest.TestCase):
    def test_generates_overlay_without_editing_upstream(self):
        module = load_script()
        self.assertNotIn(
            "ET.indent(",
            SCRIPT_PATH.read_text(encoding="utf-8"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launch_dir = (
                root
                / "fuel_ws"
                / "src"
                / "FUEL"
                / "fuel_planner"
                / "exploration_manager"
                / "launch"
            )
            launch_dir.mkdir(parents=True)
            exploration = launch_dir / "exploration.launch"
            simulator = launch_dir / "simulator.xml"
            algorithm = launch_dir / "algorithm.xml"
            exploration.write_text(EXPLORATION_XML, encoding="utf-8", newline="\n")
            simulator.write_text(SIMULATOR_XML, encoding="utf-8", newline="\n")
            algorithm.write_text("<launch/>\n", encoding="utf-8", newline="\n")
            upstream_before = {
                path.name: path.read_bytes()
                for path in (exploration, simulator, algorithm)
            }

            pcd = (
                REPOSITORY_ROOT
                / "research"
                / "01_ruins_environment"
                / "maps"
                / "pcd"
                / "Ruins-Urban-01_base.pcd"
            )
            output = root / "generated"
            generated, manifest_path = module.generate_overlay(
                root / "fuel_ws", pcd, output, "base"
            )

            generated_root = ET.parse(generated).getroot()
            self.assertEqual(
                module.direct_arg(generated_root, "init_x").get("value"), "-19.2"
            )
            simulator_include = module.include_by_suffix(
                generated_root, "fuel_simulator_base.launch"
            )
            include_args = {
                element.get("name"): element.get("value")
                for element in simulator_include.findall("arg")
            }
            self.assertEqual(include_args["box_max_z"], "7.65")

            generated_simulator = ET.parse(
                output / "fuel_simulator_base.launch"
            ).getroot()
            self.assertEqual(
                module.map_publisher(generated_simulator).get("args"),
                str(pcd.resolve()),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(
                manifest["scientific_boundary"]["upstream_checkout_modified"]
            )
            self.assertEqual(
                manifest["scientific_boundary"]["planner_prior_information"],
                ["exploration_box", "initial_pose"],
            )
            self.assertFalse(
                manifest["scientific_boundary"]["planner_prior_map"]
            )
            self.assertFalse(
                manifest["scientific_boundary"]["planner_prior_obstacle_layout"]
            )
            self.assertFalse(
                manifest["scientific_boundary"]["planner_predefined_waypoints"]
            )
            self.assertFalse(
                manifest["scientific_boundary"]["planner_predefined_goal"]
            )

            upstream_after = {
                path.name: path.read_bytes()
                for path in (exploration, simulator, algorithm)
            }
            self.assertEqual(upstream_before, upstream_after)

    def test_start_signal_contains_no_target_offset(self):
        source = (
            STAGE_ROOT / "scripts" / "trigger_exploration.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "goal.pose.position.x = self.odometry.pose.pose.position.x",
            source,
        )
        self.assertIn(
            "goal.pose.position.y = self.odometry.pose.pose.position.y",
            source,
        )
        self.assertIn(
            "goal.pose.position.z = self.odometry.pose.pose.position.z",
            source,
        )
        self.assertNotIn("position.x +", source)
        self.assertNotIn("position.y +", source)
        self.assertNotIn("position.z +", source)


if __name__ == "__main__":
    unittest.main()
