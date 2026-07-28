#!/usr/bin/env python3
"""Extract auditable effective parameters from a generated FUEL overlay."""

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
            }
        )
    payload = {
        "schema_version": 1,
        "overlay_manifest": str(arguments.overlay_manifest.resolve()),
        "scene_profile": manifest.get("variant"),
        "scientific_boundary": manifest.get("scientific_boundary", {}),
        "sources": sources,
        "note": (
            "This snapshot is read-only. It records effective launch parameters "
            "before a sensitivity study; it does not modify FUEL or provide a route."
        ),
    }
    output = arguments.output or arguments.overlay_manifest.with_name("effective_fuel_config.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
