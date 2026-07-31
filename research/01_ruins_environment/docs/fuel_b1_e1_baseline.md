# B1: FUEL Single-UAV Frontier Baseline in E1

This is the first executable experiment in the cooperative-exploration study.
It is a functional baseline, not a paper result and not a multi-UAV method.
The frozen study-wide metric definitions are in
[`evaluation_protocol.md`](evaluation_protocol.md).

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

The project RViz launch reuses FUEL's own verified `traj.rviz`. For the first
run, add a `Marker` display for `/planning_vis/frontier`, then use RViz `File`
-> `Save Config As` to store it at `~/.ros/fuel_b1_frontier.rviz`. Future runs
can open that saved profile directly with `rviz -d ~/.ros/fuel_b1_frontier.rviz`.
The visualizer sends no command to the planner.

After FUEL prints `finish exploration.`, the recorder waits three seconds,
writes the final online map and exits. It also writes a read-only online-map
snapshot every 20 seconds. Snapshots are not available to FUEL and are used
only after the run to derive the map-quality curve and time-to-coverage
metrics. Evaluate that map only after the run:

```bash
rosrun ruins_urban_01 evaluate_surface_map.py \
  --truth-pcd /tmp/damage_building_suite_v1/pcd/Coop-Building-E1-Structured-Interior_interior_reference.pcd \
  --observed-pcd /tmp/fuel_b1_e1_trial_01/final_online_occupancy.pcd \
  --snapshots-csv /tmp/fuel_b1_e1_trial_01/snapshots.csv \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --output /tmp/fuel_b1_e1_trial_01/map_quality.json
```

The resulting `trial_summary.json` contains completion time, flight-path
length, online-map growth and Frontier message statistics. `map_quality.json`
contains offline Precision, Recall and F1, and, for newly collected trials,
the surface-recall curve plus `T80`, `T90` and `T95`. `T90` means the first
time at which the offline interior-reference surface recall reaches 90%; it is
`null` if the trial never reaches that threshold. The primary reference excludes
exterior envelope faces and obstacle bottom faces that cannot be observed from
inside the building. The full PCD remains available as a stricter supplementary
reference. The evaluator never runs during the experiment and cannot affect
planning.

The launch overlay and manifest live in `/tmp`; upstream FUEL is not modified.
Review `manifest.json` before each run. A later recorder will collect map
quality, completion time, trajectory length and map-growth data.

## Five-Trial Paper Summary

After all five completed B1 trials have been archived outside `/tmp`, create a
read-only paper table summary. The command does not open ROS topics, modify a
map or rerun a planner:

```bash
rosrun ruins_urban_01 summarize_b1_trials.py \
  ~/uav_experiment_results/B1_E1_rep01 \
  ~/uav_experiment_results/B1_E1_rep02 \
  ~/uav_experiment_results/B1_E1_rep03 \
  ~/uav_experiment_results/B1_E1_rep04 \
  ~/uav_experiment_results/B1_E1_rep05 \
  --output ~/uav_experiment_results/B1_E1_summary.json \
  --per-trial-csv ~/uav_experiment_results/B1_E1_per_trial.csv
```

The JSON reports each trial and `mean +/- sample standard deviation` for map
Precision, Recall, F1, `T80/T90/T95`, mission duration and path length. A
coverage threshold that no trial reaches remains `null`; it is never replaced
by a timeout. The CSV is the source for the B1 row of the later paper table.
