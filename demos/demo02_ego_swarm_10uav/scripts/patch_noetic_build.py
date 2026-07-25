#!/usr/bin/env python3
"""Apply the recorded ROS Noetic message dependency fix, with strict guards."""

from __future__ import annotations

import argparse
from pathlib import Path


OLD = "add_dependencies(multi_map_visualization multi_map_server_messages_cpp)"
NEW = (
    "add_dependencies(multi_map_visualization "
    "${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    cmake = (
        args.workspace
        / "src"
        / "uav_simulator"
        / "Utils"
        / "multi_map_server"
        / "CMakeLists.txt"
    )
    if not cmake.is_file():
        raise SystemExit(f"Expected upstream file not found: {cmake}")

    text = cmake.read_text(encoding="utf-8")
    if NEW in text:
        print("Noetic dependency fix is already present.")
        return
    if text.count(OLD) != 1:
        raise SystemExit("Expected upstream dependency line was not found exactly once.")

    backup = cmake.with_suffix(".txt.before_ruins_demo")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    cmake.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"Patched: {cmake}")


if __name__ == "__main__":
    main()

