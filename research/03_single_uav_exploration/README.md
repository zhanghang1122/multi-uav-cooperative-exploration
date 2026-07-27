# 03. Single-UAV Autonomous Exploration Baseline

This ROS package adapts the official FUEL single-UAV exploration stack to the
fixed Ruins-Urban-01 benchmark maps. It is the control baseline for the later
three-UAV coordination method.

The package name is `ruins_single_uav_exploration`.

## Why This Stage Exists

Stage 02 proves only that local sensor observations can update an online 3D
map at the initial pose. Stage 03 adds motion exclusively through autonomous
exploration. FUEL detects frontiers from its current occupancy map, chooses
viewpoints, plans a collision-free trajectory, and repeats until no frontier
remains.

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
- a variant-specific exploration box inset by the UAV safety radius;
- the validated entrance pose `[-19.2, 0.0, 1.35]`;
- all otherwise unchanged official FUEL algorithm parameters.

The map dimensions and exploration box describe only where the UAV is allowed
to search. They reveal nothing about walls, rubble, passages, dead ends, or
vertical connections inside that box.

The vertical search limits follow the modeled flight levels. `base` is limited
to `0.35-2.65 m` because it contains no upper navigation layer. `medium` and
`complex` use `0.35-5.00 m` to include their `4.55 m` upper flight level while
keeping the UAV center below the upper corridor wall tops. These are workspace
bounds, not a route or obstacle map.

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

Run one uninterrupted headless trial. This is the primary validation path;
RViz is not required for planning or map generation:

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_single_uav_exploration autonomous_trial.launch \
  exploration_launch:=/tmp/ruins_fuel_overlay/base/fuel_exploration_base.launch \
  duration_s:=1800 \
  result_file:=/tmp/ruins_fuel_base_runtime.json \
  map_file:=/tmp/ruins_fuel_base_final.pcd
```

The launch starts the official FUEL simulator, the position-neutral trigger,
the runtime monitor, and final map capture. It contains no RViz node, waypoint
sequence, patrol route, or target coordinate. It ends when FUEL reports
`finish exploration.` or when the 30-minute timeout is reached. A timeout is
recorded as a failed, incomplete trial.

After a completed trial, compute an offline occupied-surface coverage metric:

```bash
rosrun ruins_single_uav_exploration evaluate_surface_coverage.py \
  --truth-pcd "$(rospack find ruins_urban_01)/maps/pcd/Ruins-Urban-01_base.pcd" \
  --observed-pcd /tmp/ruins_fuel_base_final.pcd \
  --resolution 0.1 \
  --tolerance-voxels 1 \
  --bounds -20.65 -15.65 0.35 20.65 15.65 2.65 \
  --output /tmp/ruins_fuel_base_coverage.json
```

The truth PCD is read only after the trial and never enters FUEL. The resulting
surface recall is a controlled comparison metric, not a claim that every
physical surface is observable from free space.

## Archive a Paper Trial

Every completed trial and every failed trial that produced a runtime report
and map must be retained in a unique result directory. Failures that stop
before map capture retain their ROS log and a failure note instead.
For the first completed `base` run:

```bash
rosrun ruins_single_uav_exploration finalize_paper_trial.py \
  --variant base \
  --runtime-json /tmp/ruins_fuel_base_runtime.json \
  --map-pcd /tmp/ruins_fuel_base_final.pcd \
  --truth-pcd "$(rospack find ruins_urban_01)/maps/pcd/Ruins-Urban-01_base.pcd" \
  --overlay-manifest /tmp/ruins_fuel_overlay/base/manifest.json \
  --run-id 20260727_0114_base_uniform_height
```

The command creates:

```text
experiments/results/<run-id>/
  manifest.json
  runtime.json
  final_occupancy.pcd
  surface_coverage_tol1.json
  surface_coverage_tol2.json
  summary.csv
  figure_reconstruction_topdown.svg
  notes.md
```

The SVG is a deterministic paper figure with simulator truth, online
reconstruction, and their top-down difference. The truth map is used only
after the run.

For interactive inspection, launch the same fixed RViz style:

```bash
roslaunch ruins_single_uav_exploration view_paper_result.launch \
  truth_pcd:="$(rospack find ruins_urban_01)/maps/pcd/Ruins-Urban-01_base.pcd" \
  result_pcd:="$(rospack find ruins_single_uav_exploration)/experiments/results/20260727_0114_base_uniform_height/final_occupancy.pcd"
```

This launch starts its own ROS master when no `roscore` is running.

## Pass Condition

The runtime report passes only when odometry, an exploration trigger, B-spline
plans, position commands, and an incrementally growing occupancy cloud are
observed and FUEL logs `finish exploration.`. Any timeout is retained as a
failed trial.

The monitor also saves the last `/sdf_map/occupancy_all` message as an ASCII
PCD. Therefore the final map used for evaluation is the map produced online by
FUEL, not the simulator truth cloud.

This stage does not use PX4 and does not implement multi-UAV coordination.
Those are separate integration and research questions.
