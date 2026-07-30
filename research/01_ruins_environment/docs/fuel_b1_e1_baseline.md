# B1: FUEL Single-UAV Frontier Baseline in E1

This is the first executable experiment in the cooperative-exploration study.
It is a functional baseline, not a paper result and not a multi-UAV method.

## Method Boundary

The baseline uses official FUEL launch files unchanged in the upstream FUEL
workspace. A generated overlay changes only:

1. the PCD used by FUEL's simulator to render local sensing;
2. map bounds and physical initial pose, derived from E1 geometry.

It does not expose the truth PCD, room list, topology, route, search target or
frontier list to FUEL's online planner. This matches FUEL's documented custom
PCD workflow: the PCD is the simulator environment and local sensing is passed
to the exploration planner. The current-pose trigger is only equivalent to the
official RViz start trigger; it is not a destination.

## Commands

First generate the scenes:

```bash
rosrun ruins_urban_01 generate_damage_building_suite.py \
  --output-dir /tmp/damage_building_suite_v1
```

Create the non-invasive E1 overlay:

```bash
rosrun ruins_urban_01 prepare_fuel_baseline_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --assets-dir /tmp/damage_building_suite_v1 \
  --scene e1_structured_interior \
  --output-dir /tmp/fuel_building_baseline_overlay
```

Run the project RViz profile, a read-only recorder, and the generated launch
in separate terminals, then start it with the position-neutral trigger:

```bash
roslaunch ruins_urban_01 fuel_b1_rviz.launch
rosrun ruins_urban_01 record_fuel_b1_trial.py \
  --scene e1_structured_interior \
  --output-dir /tmp/fuel_b1_e1_trial_01
roslaunch ruins_urban_01 run_fuel_overlay.launch \
  overlay_file:=/tmp/fuel_building_baseline_overlay/fuel_e1_structured_interior_baseline.launch
rosrun ruins_urban_01 trigger_position_neutral_exploration.py
```

The project RViz profile fixes its frame to `world` and uses a `Marker` display
for `/planning_vis/frontier`. It visualizes the online occupancy map, current
frontier markers, FUEL trajectory and candidate viewpoints only. It sends no
command to the planner.

After FUEL prints `finish exploration.`, the recorder waits three seconds,
writes the final online map and exits. Evaluate that map only after the run:

```bash
rosrun ruins_urban_01 evaluate_surface_map.py \
  --truth-pcd /tmp/damage_building_suite_v1/pcd/Coop-Building-E1-Structured-Interior.pcd \
  --observed-pcd /tmp/fuel_b1_e1_trial_01/final_online_occupancy.pcd \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --output /tmp/fuel_b1_e1_trial_01/map_quality.json
```

The resulting `trial_summary.json` contains completion time, flight-path
length, online-map growth and Frontier message statistics. `map_quality.json`
contains offline Precision, Recall and F1. The evaluator never runs during the
experiment and cannot affect planning.

The launch overlay and manifest live in `/tmp`; upstream FUEL is not modified.
Review `manifest.json` before each run. A later recorder will collect map
quality, completion time, trajectory length and map-growth data.
