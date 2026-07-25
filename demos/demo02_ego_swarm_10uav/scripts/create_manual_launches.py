#!/usr/bin/env python3
"""Generate the manual-trigger wrappers used in the recorded ten-agent demo."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected {label} exactly once; upstream layout changed.")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.workspace / "src" / "planner" / "plan_manage" / "launch"
    required = ("advanced_param.xml", "run_in_sim.launch", "swarm.launch")
    for name in required:
        if not (source / name).is_file():
            raise SystemExit(f"Expected upstream launch file not found: {source / name}")

    args.output.mkdir(parents=True, exist_ok=True)

    advanced = (source / "advanced_param.xml").read_text(encoding="utf-8")
    advanced = replace_once(
        advanced,
        'name="fsm/realworld_experiment" value="false"',
        'name="fsm/realworld_experiment" value="true"',
        "realworld_experiment setting",
    )
    (args.output / "manual_advanced_param.xml").write_text(
        advanced, encoding="utf-8"
    )

    run_sim = (source / "run_in_sim.launch").read_text(encoding="utf-8")
    run_sim = replace_once(
        run_sim,
        "$(find ego_planner)/launch/advanced_param.xml",
        str(args.output / "manual_advanced_param.xml"),
        "advanced parameter include",
    )
    (args.output / "manual_run_in_sim.launch").write_text(run_sim, encoding="utf-8")

    swarm = (source / "swarm.launch").read_text(encoding="utf-8")
    swarm = replace_once(
        swarm,
        "$(find ego_planner)/launch/run_in_sim.launch",
        str(args.output / "manual_run_in_sim.launch"),
        "run_in_sim include",
    )
    (args.output / "manual_swarm.launch").write_text(swarm, encoding="utf-8")

    simple = f"""<launch>
  <include file="$(find ego_planner)/launch/rviz.launch"/>
  <include file="{args.output / 'manual_swarm.launch'}"/>
</launch>
"""
    (args.output / "manual_simple_run.launch").write_text(simple, encoding="utf-8")
    print(f"Generated guarded launch wrappers in {args.output}")


if __name__ == "__main__":
    main()

