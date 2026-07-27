#!/usr/bin/env python3
"""Validate an ASCII XYZ PCD and report its measured bounds."""

import argparse
import json
import math
from pathlib import Path


def inspect(path):
    header = {}
    measured_points = 0
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]

    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, _, value = stripped.partition(" ")
            header[key] = value.strip()
            if key == "DATA":
                break

        fields = header.get("FIELDS", "").split()
        if fields[:3] != ["x", "y", "z"]:
            raise ValueError("PCD must begin with x y z fields")
        if header.get("DATA") != "ascii":
            raise ValueError("only ASCII PCD is supported by this inspector")

        for line_number, line in enumerate(stream, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            values = stripped.split()
            if len(values) < 3:
                raise ValueError(f"invalid point row {line_number}")
            xyz = [float(values[index]) for index in range(3)]
            for axis in range(3):
                minimum[axis] = min(minimum[axis], xyz[axis])
                maximum[axis] = max(maximum[axis], xyz[axis])
            measured_points += 1

    declared_points = int(header.get("POINTS", "0"))
    if declared_points != measured_points:
        raise ValueError(
            f"declared {declared_points} points but measured {measured_points}"
        )

    return {
        "schema_version": 1,
        "file": path.name,
        "encoding": header["DATA"],
        "fields": fields,
        "points": measured_points,
        "bounds_m": {
            "min": [round(value, 6) for value in minimum],
            "max": [round(value, 6) for value in maximum],
        },
        "extent_m": [
            round(maximum[index] - minimum[index], 6) for index in range(3)
        ],
        "passed": measured_points > 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pcd", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = inspect(arguments.pcd.resolve())
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with arguments.output.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
