#!/usr/bin/env python3
"""Prepare a non-invasive FUEL launch overlay for one generated building scene.

FUEL's official simulator uses a global PCD only to render a local sensor
stream.  This helper retains that interface and changes only the simulator PCD,
workspace bounds and physical initial pose.  It does not add a route, frontier,
room label, exploration goal, map topic or task allocation to FUEL.
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


SCENE_FILES = {
    "e1_structured_interior": "Coop-Building-E1-Structured-Interior",
    "e2_damaged_building": "Coop-Building-E2-Damaged-Building",
    "e3_industrial_wing": "Coop-Building-E3-Industrial-Wing",
}


def write_text_lf(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def write_json(path, value):
    write_text_lf(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def find_source_launches(fuel_workspace):
    root = os.path.join(fuel_workspace, "src", "FUEL", "fuel_planner", "exploration_manager", "launch")
    exploration = os.path.join(root, "exploration.launch")
    simulator = os.path.join(root, "simulator.xml")
    missing = [path for path in (exploration, simulator) if not os.path.isfile(path)]
    if missing:
        raise RuntimeError("FUEL official launch files were not found: " + ", ".join(missing))
    return exploration, simulator


def set_arg(root, name, value):
    for element in root.findall("arg"):
        if element.get("name") == name:
            element.set("value", str(value))
            return
    raise RuntimeError("expected FUEL launch arg is missing: " + name)


def write_xml(tree, path):
    # ElementTree.indent is unavailable on Ubuntu 20.04 Python 3.8.
    tree.write(path, encoding="utf-8", xml_declaration=True)
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n")


def prepare_simulator(source, output, pcd_path):
    tree = ET.parse(source)
    root = tree.getroot()
    pcd_nodes = [node for node in root.findall("node") if node.get("pkg") == "map_generator" and node.get("type") == "map_pub"]
    if len(pcd_nodes) != 1:
        raise RuntimeError("expected exactly one official FUEL map_generator/map_pub node")
    pcd_nodes[0].set("args", pcd_path)
    write_xml(tree, output)


def prepare_exploration(source, output, simulator_overlay, scene):
    tree = ET.parse(source)
    root = tree.getroot()
    width, depth, height = scene["size"]
    entry_x, entry_y, entry_z = scene["entry"]
    set_arg(root, "map_size_x", width)
    set_arg(root, "map_size_y", depth)
    set_arg(root, "map_size_z", height)
    set_arg(root, "init_x", entry_x)
    set_arg(root, "init_y", entry_y)
    set_arg(root, "init_z", entry_z)

    algorithm_includes = [include for include in root.findall("include") if include.get("file") == "$(find exploration_manager)/launch/algorithm.xml"]
    if len(algorithm_includes) != 1:
        raise RuntimeError("official FUEL algorithm include was not found")
    algorithm = algorithm_includes[0]
    for name, value in (
        ("box_min_x", -width / 2.0), ("box_min_y", -depth / 2.0), ("box_min_z", 0.0),
        ("box_max_x", width / 2.0), ("box_max_y", depth / 2.0), ("box_max_z", height),
    ):
        for argument in algorithm.findall("arg"):
            if argument.get("name") == name:
                argument.set("value", "{:.4f}".format(value))
                break
        else:
            raise RuntimeError("official FUEL algorithm arg was not found: " + name)

    simulator_includes = [include for include in root.findall("include") if include.get("file") == "$(find exploration_manager)/launch/simulator.xml"]
    if len(simulator_includes) != 1:
        raise RuntimeError("official FUEL simulator include was not found")
    simulator_includes[0].set("file", simulator_overlay)
    write_xml(tree, output)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuel-workspace", default=os.path.expanduser("~/fuel_ws"))
    parser.add_argument("--assets-dir", default="/tmp/damage_building_suite_v1")
    parser.add_argument("--scene", choices=sorted(SCENE_FILES), default="e1_structured_interior")
    parser.add_argument("--output-dir", default="/tmp/fuel_building_baseline_overlay")
    return parser.parse_args()


def main():
    args = parse_args()
    stem = SCENE_FILES[args.scene]
    assets_dir = os.path.abspath(os.path.expanduser(args.assets_dir))
    pcd_path = os.path.join(assets_dir, "pcd", stem + ".pcd")
    report_path = os.path.join(assets_dir, "validation", stem + ".json")
    if not os.path.isfile(pcd_path) or not os.path.isfile(report_path):
        raise SystemExit("scene assets are missing; generate the suite first: " + assets_dir)
    report = load_json(report_path)
    scene = report.get("scene", {})
    if scene.get("key") != args.scene:
        raise SystemExit("scene validation report does not match requested scene")
    reachability = report.get("reachability", {})
    if not reachability.get("passed"):
        raise SystemExit("scene geometry QA did not pass; do not prepare a runtime overlay")

    source_exploration, source_simulator = find_source_launches(os.path.abspath(os.path.expanduser(args.fuel_workspace)))
    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    os.makedirs(output_dir, exist_ok=True)
    simulator_overlay = os.path.join(output_dir, "simulator_" + args.scene + ".xml")
    launch_overlay = os.path.join(output_dir, "fuel_" + args.scene + "_baseline.launch")
    prepare_simulator(source_simulator, simulator_overlay, pcd_path)
    prepare_exploration(source_exploration, launch_overlay, simulator_overlay, scene)

    manifest = {
        "schema_version": 1,
        "method_id": "B1_fuel_frontier_single_uav",
        "scene": args.scene,
        "launch": launch_overlay,
        "simulator_overlay": simulator_overlay,
        "source_fuel_launches": {"exploration": source_exploration, "simulator": source_simulator},
        "simulator_truth_pcd": pcd_path,
        "runtime_contract": {
            "pcd_role": "simulator_global_map_for_local_sensor_rendering_only",
            "truth_pcd_supplied_to_online_planner": False,
            "route_prior_used": False,
            "goal_prior_used": False,
            "room_or_topology_prior_used": False,
            "exploration_start": "position-neutral trigger only",
        },
        "geometry_qa": reachability,
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    write_json(manifest_path, manifest)
    print(json.dumps({"launch": launch_overlay, "manifest": manifest_path, "scene": args.scene}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
