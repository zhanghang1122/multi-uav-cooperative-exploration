#!/usr/bin/env python3
"""Read-only audit of an E2 FUEL overlay before a runtime trial.

The script verifies that the generated overlay carries the frozen indoor
flight-volume bounds into FUEL's official algorithm include.  It does not
start ROS, publish a command, or modify the FUEL checkout.
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


EXPECTED = {
    "box_min_x": -23.0,
    "box_max_x": 23.0,
    "box_min_y": -18.0,
    "box_max_y": 18.0,
    "box_min_z": 0.80,
    "box_max_z": 2.05,
}


def close_enough(actual, expected):
    return abs(actual - expected) <= 1e-4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    overlay = os.path.abspath(os.path.expanduser(args.overlay_file))
    if not os.path.isfile(overlay):
        raise SystemExit("overlay file is missing: " + overlay)

    root = ET.parse(overlay).getroot()
    includes = [
        include for include in root.findall("include")
        if include.get("file") == "$(find exploration_manager)/launch/algorithm.xml"
    ]
    if len(includes) != 1:
        raise SystemExit("expected exactly one official FUEL algorithm include")

    supplied = {}
    for argument in includes[0].findall("arg"):
        name = argument.get("name")
        if name in EXPECTED:
            try:
                supplied[name] = float(argument.get("value"))
            except (TypeError, ValueError):
                supplied[name] = None

    checks = {
        name: {
            "expected": expected,
            "actual": supplied.get(name),
            "passed": supplied.get(name) is not None and close_enough(supplied[name], expected),
        }
        for name, expected in EXPECTED.items()
    }
    result = {
        "schema_version": 1,
        "mode": "read_only_overlay_contract_audit",
        "overlay_file": overlay,
        "checks": checks,
        "passed": all(item["passed"] for item in checks.values()),
        "interpretation": (
            "This verifies only the generated FUEL launch configuration. "
            "It does not prove that a running trial remains in bounds; the "
            "post-trial trajectory flight-envelope audit is separately required."
        ),
    }
    destination = os.path.abspath(os.path.expanduser(args.output))
    parent = os.path.dirname(destination)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(destination, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
