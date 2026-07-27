# 03. Single-UAV Autonomous Exploration Baseline

This ROS package adapts the official FUEL single-UAV exploration stack to the
fixed Ruins-Urban-01 benchmark maps. It is the control baseline for the later
three-UAV coordination method.

The package name is `ruins_single_uav_exploration`.

## Why This Stage Exists

Stage 02 proves only that local sensor observations can grow an online 3D map
along a declared reference route. Stage 03 removes that route. FUEL detects
frontiers from its current occupancy map, chooses viewpoints, plans a
collision-free trajectory, and repeats until no frontier remains.

The planner receives only the exploration box and the validated initial pose.
It receives no prebuilt map, obstacle layout, target coordinate, waypoint
sequence, or manually divided region. The complete PCD is simulator truth and
is connected only to FUEL's local sensor renderer.

The one-shot `2D Nav Goal` message follows the official FUEL startup interface:
it is a start signal, not a destination for the exploration task. After that
signal, every viewpoint and trajectory is generated online from frontiers in
the currently observed occupancy map. Exploration is complete when no valid
frontier remains inside the configured box.

## Upstream Boundary

FUEL is GPL-3.0 and remains in a separate `~/fuel_ws`. This repository does
not vendor or rewrite its source. `prepare_fuel_overlay.py` reads the installed
upstream launch files and writes temporary launch copies containing:

- the selected Ruins-Urban-01 PCD path;
- the 42 m by 32 m by 10 m internal map size;
- an exploration box inset by the UAV safety radius;
- the validated entrance pose `[-19.2, 0.0, 1.35]`;
- all otherwise unchanged official FUEL algorithm parameters.

The map dimensions and exploration box describe only where the UAV is allowed
to search. They reveal nothing about walls, rubble, passages, dead ends, or
vertical connections inside that box.

The generated manifest records SHA-256 hashes of every input. The upstream
checkout is not modified.

## Required Order

1. complete the Stage 02 Ubuntu runtime test;
2. run the official FUEL office example unchanged;
3. generate and run the `base` overlay;
4. repeat on `medium`;
5. repeat on `complex`;
6. only then use unseen seeded ruins.

## Quick Start

After installing FUEL and rebuilding the paper workspace as described in
[`docs/ubuntu20_setup.md`](docs/ubuntu20_setup.md):

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash

rosrun ruins_single_uav_exploration prepare_fuel_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --variant base \
  --output-dir /tmp/ruins_fuel_overlay/base

roslaunch /tmp/ruins_fuel_overlay/base/fuel_exploration_base.launch
```

Start RViz in another terminal:

```bash
source ~/fuel_ws/devel/setup.bash
roslaunch exploration_manager rviz.launch
```

Start evidence capture and then the one-shot trigger:

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_single_uav_exploration runtime_validation.launch
```

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_single_uav_exploration automatic_trigger.launch
```

## Pass Condition

The runtime report passes only when odometry, an exploration trigger, B-spline
plans, position commands, and an incrementally growing occupancy cloud are
observed and FUEL logs `finish exploration.`. Any timeout is retained as a
failed trial.

This stage does not use PX4 and does not implement multi-UAV coordination.
Those are separate integration and research questions.
