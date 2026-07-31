# B1: FUEL Single-UAV Frontier Baseline in E2

E2 is the fixed primary damaged-building scene for the paper comparison. This
document defines the B1 reference experiment only: one UAV, official FUEL
Frontier exploration, five independent repetitions. It is the reference row
against which B2, B3 and P will later be compared on the same E2 scene.

E2 contains 16 rooms, 4 loops, 6 dead ends, 4 bottlenecks, 6 bounded damage
clusters and 8 vertical/overhead structures. The scene size is approximately
42 m x 32 m x 4.2 m. Its geometry and the planning-clearance validation are
generated deterministically by the scene generator; do not change the scene
or FUEL parameters between B1 repetitions.

## Fixed Online Boundary

The online planner receives only FUEL's normal local sensing stream. It does
not receive a route, goal location, room list, topology, Frontier list or
truth map. The current-pose start signal only starts FUEL's official
exploration state machine. The truth PCD is used after termination by the
offline evaluator, never by a ROS node while the UAV is exploring.

## One-Time Preparation

In a terminal with ROS Noetic, FUEL and the project workspace sourced, create
the deterministic assets and a non-invasive FUEL overlay:

```bash
rosrun ruins_urban_01 generate_damage_building_suite.py \
  --output-dir /tmp/damage_building_suite_v1

rosrun ruins_urban_01 prepare_fuel_baseline_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --assets-dir /tmp/damage_building_suite_v1 \
  --scene e2_damaged_building \
  --output-dir /tmp/fuel_building_baseline_overlay
```

Before the first run, inspect the resulting
`/tmp/fuel_building_baseline_overlay/manifest.json`. Its runtime contract must
state `route_prior_used: false`, `goal_prior_used: false` and
`truth_pcd_supplied_to_online_planner: false`.

## Five Repetitions

Run one repetition at a time. Start the generated FUEL overlay, the project
RViz profile and the read-only recorder in separate terminals:

```bash
roslaunch ruins_urban_01 run_fuel_overlay.launch \
  overlay_file:=/tmp/fuel_building_baseline_overlay/fuel_e2_damaged_building_baseline.launch
```

```bash
roslaunch ruins_urban_01 fuel_b1_rviz.launch
```

```bash
rosrun ruins_urban_01 record_fuel_b1_trial.py \
  --scene e2_damaged_building \
  --output-dir /tmp/fuel_b1_e2_rep01
```

Once the recorder reports that it has received odometry and online occupancy,
issue the position-neutral trigger in a fourth terminal:

```bash
rosrun ruins_urban_01 trigger_position_neutral_exploration.py
```

The trigger process exits immediately by design. Let FUEL run until it reports
`finish exploration.`. The recorder then waits three seconds, writes the final
online map and exits. Repeat with only the output suffix changed:

```text
/tmp/fuel_b1_e2_rep01
/tmp/fuel_b1_e2_rep02
/tmp/fuel_b1_e2_rep03
/tmp/fuel_b1_e2_rep04
/tmp/fuel_b1_e2_rep05
```

Do not run two repetitions concurrently. Do not add RViz navigation goals.

## Offline Evaluation and Archiving

After each completed run, evaluate the map against the E2 interior reference:

```bash
RUN=/tmp/fuel_b1_e2_rep01
TRUTH=/tmp/damage_building_suite_v1/pcd/Coop-Building-E2-Damaged-Building_interior_reference.pcd

rosrun ruins_urban_01 evaluate_surface_map.py \
  --truth-pcd "$TRUTH" \
  --observed-pcd "$RUN/final_online_occupancy.pcd" \
  --snapshots-csv "$RUN/snapshots.csv" \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --output "$RUN/map_quality.json"
```

Archive each completed directory outside `/tmp` before the next long session:

```bash
mkdir -p ~/uav_experiment_results
cp -a /tmp/fuel_b1_e2_rep01 ~/uav_experiment_results/B1_E2_rep01
```

When all five runs have passed, generate the paper-table source data without
opening ROS or rerunning a planner:

```bash
rosrun ruins_urban_01 summarize_b1_trials.py \
  ~/uav_experiment_results/B1_E2_rep01 \
  ~/uav_experiment_results/B1_E2_rep02 \
  ~/uav_experiment_results/B1_E2_rep03 \
  ~/uav_experiment_results/B1_E2_rep04 \
  ~/uav_experiment_results/B1_E2_rep05 \
  --output ~/uav_experiment_results/B1_E2_summary.json \
  --per-trial-csv ~/uav_experiment_results/B1_E2_per_trial.csv
```

The required B1 outputs are map Precision, Recall, F1, T80/T90/T95, completion
time, path length and map-growth snapshots. They are a single-UAV reference,
not evidence of cooperative benefit. E2 B2, B3 and P will use the same scene,
sensor configuration, map reference and five-repetition protocol.
