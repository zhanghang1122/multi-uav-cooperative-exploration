#!/usr/bin/env python3
"""Extract read-only parameters and ROS interfaces from a FUEL overlay."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


INTERESTING_TOKENS = (
    "sensing",
    "horizon",
    "range",
    "resolution",
    "inflation",
    "clearance",
    "velocity",
    "acceleration",
    "yaw",
    "box_",
    "map_size",
    "init_",
)


def parse_xml_parameters(path):
    root = ET.parse(path).getroot()
    parameters = []
    for element in root.iter():
        if element.tag not in ("arg", "param"):
            continue
        name = element.get("name")
        value = element.get("value", element.get("default"))
        if name is None or value is None:
            continue
        if any(token in name.lower() for token in INTERESTING_TOKENS):
            parameters.append({"name": name, "value": value, "tag": element.tag})
    return parameters


def parse_xml_interfaces(path):
    """Return launch nodes and their explicit remaps without resolving ROS args.

    The generated overlay is a faithful copy of the official FUEL launch wiring.
    Keeping unresolved ``$(find ...)`` and argument substitutions is intentional:
    this tool records what the launch file declares and never infers a topic from
    a node name.  That prevents a global mapper from being wired to a guessed
    visualization cloud.
    """
    root = ET.parse(path).getroot()
    nodes = []
    for element in root.iter("node"):
        remaps = []
        for remap in element.findall("remap"):
            remaps.append(
                {
                    "from": remap.get("from", ""),
                    "to": remap.get("to", ""),
                }
            )
        nodes.append(
            {
                "name": element.get("name", ""),
                "package": element.get("pkg", ""),
                "type": element.get("type", ""),
                "namespace": element.get("ns", ""),
                "args": element.get("args", ""),
                "output": element.get("output", ""),
                "remaps": remaps,
            }
        )
    includes = []
    for element in root.iter("include"):
        includes.append(
            {
                "file": element.get("file", ""),
                "arguments": [
                    {"name": argument.get("name", ""), "value": argument.get("value", "")}
                    for argument in element.findall("arg")
                ],
            }
        )
    return {"nodes": nodes, "includes": includes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("overlay_manifest", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    manifest = json.loads(arguments.overlay_manifest.read_text(encoding="utf-8"))
    paths = {
        "generated_exploration_launch": Path(
            manifest["outputs"]["exploration_launch"]
        ),
        "generated_simulator_launch": Path(manifest["outputs"]["simulator_launch"]),
        "upstream_algorithm_launch": Path(manifest["inputs"]["algorithm_launch"]["path"]),
    }
    sources = []
    for label, path in paths.items():
        if not path.is_file():
            sources.append({"label": label, "path": str(path), "available": False, "parameters": []})
            continue
        sources.append(
            {
                "label": label,
                "path": str(path.resolve()),
                "available": True,
                "parameters": parse_xml_parameters(path),
                "interfaces": parse_xml_interfaces(path),
            }
        )
    payload = {
        "schema_version": 2,
        "overlay_manifest": str(arguments.overlay_manifest.resolve()),
        "scene_profile": manifest.get("variant"),
        "scientific_boundary": manifest.get("scientific_boundary", {}),
        "sources": sources,
        "note": (
            "This snapshot is read-only. It records explicit launch parameters, "
            "nodes, and remaps before a mapping integration. It does not modify "
            "FUEL, infer an interface from names, or provide a route."
        ),
    }
    output = arguments.output or arguments.overlay_manifest.with_name("effective_fuel_config.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
