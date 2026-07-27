#!/usr/bin/env python3
"""Validate the paper repository, historical demos, and ruins module."""

from __future__ import annotations

import ast
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_ROOT = ROOT / "research" / "01_ruins_environment"
MAPPING_ROOT = ROOT / "research" / "02_mapping_baseline"
DEMOS_ROOT = ROOT / "demos"
VARIANTS = ("base", "medium", "complex")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {relative(path)}")
    elif path.stat().st_size == 0:
        errors.append(f"empty file: {relative(path)}")


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
        errors.append(f"unsupported PCD encoding: {relative(path)}")
    try:
        points = int(header.get("POINTS", "0"))
    except ValueError:
        points = 0
    if points <= 0:
        errors.append(f"invalid PCD point count: {relative(path)}")


def check_python(path: Path, errors: list[str]) -> None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        errors.append(f"invalid Python {relative(path)}: {exc}")


def check_xml(path: Path, errors: list[str]) -> None:
    try:
        ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        errors.append(f"invalid XML {relative(path)}: {exc}")


def check_lf(path: Path, errors: list[str]) -> None:
    if b"\r\n" in path.read_bytes():
        errors.append(f"CRLF line endings are unsafe for Ubuntu: {relative(path)}")


def main() -> int:
    errors: list[str] = []

    root_files = (
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "CHANGELOG.md",
        "THIRD_PARTY.md",
        "docs/demo_audit.md",
        "research/README.md",
    )
    for name in root_files:
        require(ROOT / name, errors)

    environment_files = (
        "README.md",
        "package.xml",
        "CMakeLists.txt",
        "setup_env.sh",
        "config/ruins_urban_01.yaml",
        "config/benchmark_seeds.yaml",
        "docs/design_basis.md",
        "docs/environment_generation.md",
        "docs/reproducibility.md",
    )
    for name in environment_files:
        require(ENV_ROOT / name, errors)

    mapping_files = (
        "README.md",
        "package.xml",
        "CMakeLists.txt",
        "status.yaml",
        "config/mapping_baseline.yaml",
        "config/reference_trajectory.yaml",
        "docs/design_basis.md",
        "docs/ubuntu20_setup.md",
        "docs/experiment_protocol.md",
        "docs/stage_summary.md",
        "launch/mapping_baseline.launch",
        "launch/marsim_single_uav_sensor.launch",
        "launch/octomap_online.launch",
        "launch/reference_trajectory.launch",
        "launch/runtime_validation.launch",
        "rviz/mapping_baseline.rviz",
        "scripts/inspect_pcd.py",
        "scripts/local_cloud_gate.py",
        "scripts/reference_trajectory.py",
        "scripts/runtime_monitor.py",
        "experiments/results/base_pcd_static_report.json",
        "experiments/results/medium_pcd_static_report.json",
        "experiments/results/complex_pcd_static_report.json",
    )
    for name in mapping_files:
        require(MAPPING_ROOT / name, errors)

    demo_files = (
        "README.md",
        "demo01_single_uav_obstacle_avoidance/README.md",
        "demo01_single_uav_obstacle_avoidance/status.yaml",
        "demo01_single_uav_obstacle_avoidance/evidence/d435i_streams.png",
        "demo01_single_uav_obstacle_avoidance/evidence/rviz_box_pointcloud.png",
        "demo01_single_uav_obstacle_avoidance/scripts/verify_perception.sh",
        "demo02_ego_swarm_10uav/README.md",
        "demo02_ego_swarm_10uav/status.yaml",
        "demo02_ego_swarm_10uav/evidence/ten_agent_run.png",
        "demo02_ego_swarm_10uav/scripts/patch_noetic_build.py",
        "demo02_ego_swarm_10uav/scripts/create_manual_launches.py",
        "demo02_ego_swarm_10uav/scripts/run.sh",
        "demo02_ego_swarm_10uav/scripts/trigger.sh",
        "demo03_fuel_exploration/README.md",
        "demo03_fuel_exploration/status.yaml",
        "demo03_fuel_exploration/evidence/fuel_map_growth.png",
        "demo03_fuel_exploration/scripts/run_rviz.sh",
        "demo03_fuel_exploration/scripts/run_exploration.sh",
    )
    for name in demo_files:
        require(DEMOS_ROOT / name, errors)

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    expected_repository = (
        "github.com/zhanghang1122/multi-uav-cooperative-exploration"
    )
    if expected_repository not in citation:
        errors.append("CITATION.cff does not identify the paper repository")
    if "version: 0.7.0" not in citation:
        errors.append("CITATION.cff version must be 0.7.0")

    package_path = ENV_ROOT / "package.xml"
    try:
        package = ET.parse(package_path).getroot()
        if package.findtext("name") != "ruins_urban_01":
            errors.append("ruins module ROS package name must be ruins_urban_01")
        if package.findtext("license") != "MIT":
            errors.append("ruins module license must match repository LICENSE")
    except (ET.ParseError, OSError) as exc:
        errors.append(f"invalid package.xml: {exc}")

    cmake = (ENV_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if "project(ruins_urban_01)" not in cmake:
        errors.append("ruins module CMake project name is incorrect")
    if "\n  demos\n" in cmake or "\n  blender\n" in cmake:
        errors.append("ruins module installs a directory that is not part of the package")

    mapping_package_path = MAPPING_ROOT / "package.xml"
    try:
        mapping_package = ET.parse(mapping_package_path).getroot()
        if mapping_package.findtext("name") != "ruins_mapping_baseline":
            errors.append(
                "mapping module ROS package name must be ruins_mapping_baseline"
            )
        if mapping_package.findtext("license") != "MIT":
            errors.append("mapping module license must match repository LICENSE")
    except (ET.ParseError, OSError) as exc:
        errors.append(f"invalid mapping package.xml: {exc}")

    mapping_cmake = (MAPPING_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    if "project(ruins_mapping_baseline)" not in mapping_cmake:
        errors.append("mapping module CMake project name is incorrect")
    if "catkin_install_python" not in mapping_cmake:
        errors.append("mapping module does not install its Python nodes")

    octomap_launch = (
        MAPPING_ROOT / "launch" / "octomap_online.launch"
    ).read_text(encoding="utf-8")
    if "/mapping/input_cloud" not in octomap_launch:
        errors.append("OctoMap input is not routed through the local-cloud gate")
    if "/map_generator/global_cloud" in octomap_launch:
        errors.append("OctoMap launch must not reference simulator truth cloud")

    mapping_status = (MAPPING_ROOT / "status.yaml").read_text(encoding="utf-8")
    expected_mapping_status = "status: implementation_ready_runtime_pending"
    if expected_mapping_status not in mapping_status:
        errors.append("mapping stage must remain runtime-pending before Ubuntu evidence")

    for variant in VARIANTS:
        report_path = (
            MAPPING_ROOT
            / "experiments"
            / "results"
            / f"{variant}_pcd_static_report.json"
        )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not report.get("passed") or report.get("points", 0) <= 0:
                errors.append(f"invalid static PCD report: {relative(report_path)}")
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid static PCD report {relative(report_path)}: {exc}")

    try:
        summary = json.loads(
            (ENV_ROOT / "validation" / "generation_summary.json").read_text(
                encoding="utf-8"
            )
        )
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"invalid generation summary: {exc}")
        summary = {}

    for variant in VARIANTS:
        check_pcd(
            ENV_ROOT / "maps" / "pcd" / f"Ruins-Urban-01_{variant}.pcd",
            errors,
        )
        require(
            ENV_ROOT / "meshes" / "obj" / f"Ruins-Urban-01_{variant}.obj",
            errors,
        )
        require(
            ENV_ROOT / "meshes" / "dae" / f"Ruins-Urban-01_{variant}.dae",
            errors,
        )
        require(
            ENV_ROOT / "gazebo" / "worlds" / f"Ruins-Urban-01_{variant}.world",
            errors,
        )
        require(
            ENV_ROOT
            / "gazebo"
            / "models"
            / f"ruins_urban_01_{variant}"
            / "model.sdf",
            errors,
        )
        require(
            ENV_ROOT
            / "validation"
            / f"Ruins-Urban-01_{variant}_validation.json",
            errors,
        )
        if not summary.get(variant, {}).get("validation", {}).get("passed"):
            errors.append(f"clearance validation did not pass for {variant}")

    xml_files = (
        list((ENV_ROOT / "launch").glob("*.launch"))
        + list((ENV_ROOT / "gazebo" / "worlds").glob("*.world"))
        + list((ENV_ROOT / "gazebo" / "models").glob("*/model.sdf"))
        + list((MAPPING_ROOT / "launch").glob("*.launch"))
        + [package_path, mapping_package_path]
    )
    for path in xml_files:
        check_xml(path, errors)

    python_files = (
        list((ENV_ROOT / "scripts").glob("*.py"))
        + list((MAPPING_ROOT / "scripts").glob("*.py"))
        + list(DEMOS_ROOT.glob("*/scripts/*.py"))
        + list((ROOT / "tools").glob("*.py"))
    )
    for path in python_files:
        check_python(path, errors)

    expected_status = {
        "demo01_single_uav_obstacle_avoidance": "incomplete_end_to_end",
        "demo02_ego_swarm_10uav": "historically_demonstrated",
        "demo03_fuel_exploration": "historically_demonstrated",
    }
    for directory, status in expected_status.items():
        text = (DEMOS_ROOT / directory / "status.yaml").read_text(
            encoding="utf-8"
        )
        if f"id: {directory}" not in text or f"status: {status}" not in text:
            errors.append(f"incorrect demo status declaration: {directory}")
        if "verified:" not in text:
            errors.append(f"missing verified evidence list: {directory}")

    forbidden_demo1 = (
        DEMOS_ROOT
        / "demo01_single_uav_obstacle_avoidance"
        / "scripts"
        / "run_avoidance.sh"
    )
    if forbidden_demo1.exists():
        errors.append("Demo 1 must not publish an unverified avoidance runner")

    text_extensions = {
        ".cff",
        ".json",
        ".launch",
        ".md",
        ".mtl",
        ".obj",
        ".pcd",
        ".py",
        ".sdf",
        ".sh",
        ".svg",
        ".world",
        ".xml",
        ".yaml",
    }
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in text_extensions:
            check_lf(path, errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository validation passed.")
    print("Checked:")
    print("- paper-repository layout and citation metadata")
    print("- three audited historical demo records")
    print("- Ruins-Urban-01 ROS/XML/PCD/mesh assets")
    print("- Stage 02 mapping package, topic isolation, launch/XML, and Python syntax")
    print("- LF line endings and clearance reports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
