#!/usr/bin/env python3
"""Validate repository structure and generated Ruins-Urban-01 assets."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("base", "medium", "complex")


def require(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path.relative_to(ROOT)}")
    elif path.stat().st_size == 0:
        errors.append(f"empty file: {path.relative_to(ROOT)}")


def check_pcd(path: Path, errors: list[str]) -> None:
    require(path, errors)
    if not path.is_file():
        return
    header: dict[str, str] = {}
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            key, _, value = line.partition(" ")
            header[key] = value.strip()
            if key == "DATA":
                break
    if header.get("DATA") != "ascii":
        errors.append(f"unsupported PCD DATA encoding in {path.relative_to(ROOT)}")
    try:
        points = int(header.get("POINTS", "0"))
    except ValueError:
        points = 0
    if points <= 0:
        errors.append(f"invalid PCD point count in {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    require(ROOT / "README.md", errors)
    require(ROOT / "LICENSE", errors)
    require(ROOT / "CITATION.cff", errors)
    require(ROOT / "package.xml", errors)
    require(ROOT / "CMakeLists.txt", errors)
    require(ROOT / "config" / "ruins_urban_01.yaml", errors)
    require(ROOT / "config" / "benchmark_seeds.yaml", errors)

    try:
        package = ET.parse(ROOT / "package.xml").getroot()
        if package.findtext("name") != "ruins_urban_01":
            errors.append("package.xml name must be ruins_urban_01")
        if package.findtext("license") != "MIT":
            errors.append("package.xml license must match LICENSE")
    except (ET.ParseError, OSError) as exc:
        errors.append(f"invalid package.xml: {exc}")

    try:
        summary = json.loads((ROOT / "validation" / "generation_summary.json").read_text())
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"invalid generation summary: {exc}")
        summary = {}

    for variant in VARIANTS:
        check_pcd(ROOT / "maps" / "pcd" / f"Ruins-Urban-01_{variant}.pcd", errors)
        require(ROOT / "meshes" / "obj" / f"Ruins-Urban-01_{variant}.obj", errors)
        require(ROOT / "meshes" / "dae" / f"Ruins-Urban-01_{variant}.dae", errors)
        require(ROOT / "gazebo" / "worlds" / f"Ruins-Urban-01_{variant}.world", errors)
        require(
            ROOT / "gazebo" / "models" / f"ruins_urban_01_{variant}" / "model.sdf",
            errors,
        )
        require(ROOT / "validation" / f"Ruins-Urban-01_{variant}_validation.json", errors)
        if not summary.get(variant, {}).get("validation", {}).get("passed"):
            errors.append(f"clearance validation did not pass for {variant}")

    for xml_file in list((ROOT / "launch").glob("*.launch")) + list(
        (ROOT / "gazebo" / "worlds").glob("*.world")
    ) + list((ROOT / "gazebo" / "models").glob("*/model.sdf")):
        try:
            ET.parse(xml_file)
        except ET.ParseError as exc:
            errors.append(f"invalid XML {xml_file.relative_to(ROOT)}: {exc}")

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository validation passed.")
    print("Checked fixed PCD, mesh, Gazebo, ROS, metadata, and clearance assets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
