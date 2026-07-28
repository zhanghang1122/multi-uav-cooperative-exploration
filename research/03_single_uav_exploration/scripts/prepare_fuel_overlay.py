#!/usr/bin/env python3
"""Generate a Ruins-Urban-01 FUEL launch overlay without editing FUEL."""

import argparse
import hashlib
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


MAP_SIZE = {"x": "42.0", "y": "32.0", "z": "10.0"}
COMMON_BOX = {
    "box_min_x": "-20.65", "box_min_y": "-15.65", "box_min_z": "0.35",
    "box_max_x": "20.65", "box_max_y": "15.65",
}
BOX_MAX_Z = {"base": "2.65", "medium": "5.00", "complex": "5.00"}
INITIAL_POSE = {"init_x": "-19.2", "init_y": "0.0", "init_z": "1.35"}


def repository_root():
    return Path(__file__).resolve().parents[3]


def exploration_box(variant):
    if variant not in BOX_MAX_Z:
        raise ValueError("unsupported ruins variant: %s" % variant)
    return dict(COMMON_BOX, box_max_z=BOX_MAX_Z[variant])


def default_pcd(variant):
    relative = Path("maps") / "pcd" / ("Ruins-Urban-01_%s.pcd" % variant)
    source_candidate = repository_root() / "research" / "01_ruins_environment" / relative
    if source_candidate.is_file():
        return source_candidate
    try:
        import rospkg
        package_candidate = Path(rospkg.RosPack().get_path("ruins_urban_01")) / relative
        if package_candidate.is_file():
            return package_candidate
    except (ImportError, Exception):
        pass
    raise FileNotFoundError("could not locate Ruins-Urban-01 PCD; source catkin_ws or pass --pcd")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_single(paths, description):
    candidates = sorted(path.resolve() for path in paths)
    if len(candidates) != 1:
        raise RuntimeError("expected one %s, found %d" % (description, len(candidates)))
    return candidates[0]


def find_fuel_launches(workspace):
    source = workspace.resolve() / "src"
    exploration = require_single(source.rglob("exploration_manager/launch/exploration.launch"), "FUEL exploration.launch")
    simulator = exploration.with_name("simulator.xml")
    algorithm = exploration.with_name("algorithm.xml")
    if not simulator.is_file() or not algorithm.is_file():
        raise FileNotFoundError("FUEL simulator.xml or algorithm.xml is missing")
    return exploration, simulator, algorithm


def validate_pcd(path):
    header = {}
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, _, value = stripped.partition(" ")
            header[key] = value.strip()
            if key == "DATA":
                break
    if header.get("DATA") != "ascii" or int(header.get("POINTS", "0")) <= 0:
        raise ValueError("FUEL overlay requires a nonempty ASCII PCD")
    if header.get("FIELDS", "").split()[:3] != ["x", "y", "z"]:
        raise ValueError("PCD must begin with x y z fields")


def direct_arg(root, name):
    for element in root.findall("arg"):
        if element.get("name") == name:
            return element
    raise ValueError("upstream launch is missing arg '%s'" % name)


def set_direct_arg(root, name, value):
    element = direct_arg(root, name)
    element.set("value", str(value))
    element.attrib.pop("default", None)


def include_by_suffix(root, suffix):
    matches = [element for element in root.findall("include") if element.get("file", "").endswith(suffix)]
    if len(matches) != 1:
        raise ValueError("expected one include ending in %s" % suffix)
    return matches[0]


def set_include_arg(include, name, value):
    for element in include.findall("arg"):
        if element.get("name") == name:
            element.set("value", str(value))
            return
    ET.SubElement(include, "arg", {"name": name, "value": str(value)})


def map_publisher(root):
    matches = [element for element in root.findall("node") if element.get("pkg") == "map_generator" and element.get("type") == "map_pub"]
    if len(matches) != 1:
        raise ValueError("expected one active FUEL map publisher")
    return matches[0]


def indent_xml(element, level=0):
    """Indent XML without Python 3.9's ElementTree.indent."""
    indentation = "\n" + level * "  "
    child_indentation = indentation + "  "
    children = list(element)
    if children:
        if not element.text or not element.text.strip():
            element.text = child_indentation
        for child in children:
            indent_xml(child, level + 1)
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = indentation
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indentation


def write_xml(tree, path):
    indent_xml(tree.getroot())
    tree.write(path, encoding="utf-8", xml_declaration=True)


def generate_overlay(workspace, pcd, output_dir, variant):
    exploration_source, simulator_source, algorithm_source = find_fuel_launches(workspace)
    pcd = pcd.resolve()
    if not pcd.is_file():
        raise FileNotFoundError("missing ruins PCD: %s" % pcd)
    validate_pcd(pcd)
    box = exploration_box(variant)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    simulator_output = output_dir / ("fuel_simulator_%s.launch" % variant)
    exploration_output = output_dir / ("fuel_exploration_%s.launch" % variant)

    simulator_tree = ET.parse(simulator_source)
    map_publisher(simulator_tree.getroot()).set("args", str(pcd))
    write_xml(simulator_tree, simulator_output)

    exploration_tree = ET.parse(exploration_source)
    root = exploration_tree.getroot()
    for axis, value in MAP_SIZE.items():
        set_direct_arg(root, "map_size_%s" % axis, value)
    for name, value in INITIAL_POSE.items():
        set_direct_arg(root, name, value)
    algorithm_include = include_by_suffix(root, "algorithm.xml")
    simulator_include = include_by_suffix(root, "simulator.xml")
    for name, value in box.items():
        set_include_arg(algorithm_include, name, value)
        set_include_arg(simulator_include, name, value)
    simulator_include.set("file", str(simulator_output))
    write_xml(exploration_tree, exploration_output)

    manifest = {
        "schema_version": 1, "variant": variant,
        "scientific_boundary": {
            "pcd_role": "simulator truth consumed by the local sensor renderer",
            "planner_prior_information": ["exploration_box", "initial_pose"],
            "planner_prior_map": False, "planner_prior_obstacle_layout": False,
            "planner_predefined_waypoints": False, "planner_predefined_goal": False,
            "upstream_checkout_modified": False,
        },
        "inputs": {
            "pcd": {"path": str(pcd), "sha256": sha256(pcd)},
            "exploration_launch": {"path": str(exploration_source), "sha256": sha256(exploration_source)},
            "simulator_launch": {"path": str(simulator_source), "sha256": sha256(simulator_source)},
            "algorithm_launch": {"path": str(algorithm_source), "sha256": sha256(algorithm_source)},
        },
        "outputs": {"exploration_launch": str(exploration_output), "simulator_launch": str(simulator_output)},
    }
    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return exploration_output, manifest_path


def main():
    parser = argparse.ArgumentParser(description="Generate temporary FUEL launch files for Ruins-Urban-01.")
    parser.add_argument("--fuel-workspace", type=Path, required=True)
    parser.add_argument("--variant", choices=sorted(BOX_MAX_Z), default="base")
    parser.add_argument("--pcd", type=Path)
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args()
    pcd = arguments.pcd or default_pcd(arguments.variant)
    output_dir = arguments.output_dir or (Path(tempfile.gettempdir()) / "ruins_fuel_overlay" / arguments.variant)
    launch_path, manifest_path = generate_overlay(arguments.fuel_workspace, pcd, output_dir, arguments.variant)
    print("Generated FUEL overlay without modifying the upstream checkout.")
    print("Launch: %s" % launch_path)
    print("Manifest: %s" % manifest_path)


if __name__ == "__main__":
    main()
