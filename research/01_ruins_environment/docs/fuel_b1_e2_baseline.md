# B1: FUEL Single-UAV Frontier Baseline in E2 Primary

E2 Primary is the fixed damaged-building scene for the paper comparison. This
document defines the B1 reference experiment only: one UAV, official FUEL
Frontier exploration, and five independent repetitions. It is the reference
row against which B2, B3 and P will later be compared on the same E2 scene.

The fixed scene is 46 m x 36 m x 4.2 m. It contains three initially occluded
first-order branches, one physical loop, five terminal or occluded pockets,
four bottleneck doorways, six local collapse clusters, twelve columns, ten
equipment obstacles, and five partial overhead elements. At FUEL's configured
0.199 m obstacle inflation, its offline geometry audit reports 100% reachable
coverable free space and a minimum declared bottleneck clearance of 0.802 m.
The indoor operating envelope is fixed at z = 0.80--2.05 m. It is lower than
the 2.35 m minimum architectural partition top after the 0.199 m planning
envelope is applied. Therefore, the UAV cannot bypass a partition by climbing
over it; it must discover and traverse a real doorway or loop. This is an
operational altitude boundary, not a physical ceiling, route, room label or
target prior. The scene, sensor setup, altitude envelope and FUEL parameters
must not change between B1 repetitions.

## Fixed Online Boundary

The online planner receives only FUEL's normal local sensing stream. It does
not receive a route, goal location, room list, topology, Frontier list or a
planner map. The simulator uses a hidden geometric PCD only to render local
sensor returns; the planner cannot read that file or its global point cloud.
For E2, this sensor source contains only interior-facing surfaces, which
removes exterior-envelope and wall-top samples that an indoor UAV cannot
observe. The current-pose start signal only starts FUEL's official exploration
state machine.

The map and sensor volume remain 4.2 m high so that vertical structure can be
observed. RViz clips only points above 2.85 m in its display topic to suppress
the mapper's upper-boundary artifact; that display filter is not consumed by
FUEL, the recorder, or the offline evaluator.

The E2 world exports continuous 0.28 m-thick box walls for Gazebo inspection.
FUEL's official simulator obtains depth observations from a PCD surface model,
not from Gazebo collision geometry. The PCD surface lattice is fixed at 0.07 m:
its maximum in-plane diagonal gap is below FUEL's 0.10 m mapping-cell width.
FUEL then forms occupied voxels online from local depth returns. This preserves
a surface-sensor model while preventing source-sampling gaps from acting as
false wall openings. RViz displays the accumulated occupancy map with a
0.10 m square size so the integrated wall structure is visible during recording.

## One-Time Preparation

In a terminal with ROS Noetic, FUEL and the project workspace sourced, create
the deterministic assets and a non-invasive FUEL overlay:

```bash
rosrun ruins_urban_01 generate_e2_primary_benchmark.py \
  --output-dir /tmp/coop_building_e2_primary

rosrun ruins_urban_01 prepare_fuel_baseline_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --assets-dir /tmp/coop_building_e2_primary \
  --scene e2_primary_damaged_interior \
  --output-dir /tmp/fuel_building_baseline_overlay
```

Before the first run, inspect the resulting
`/tmp/fuel_building_baseline_overlay/manifest.json`. Its runtime contract must
state `route_prior_used: false`, `goal_prior_used: false` and
`truth_pcd_supplied_to_online_planner: false`.

## Five Repetitions

Run one repetition at a time through the fixed trial launcher. It starts the
generated FUEL overlay, the project RViz profile, the read-only recorder and a
delayed position-neutral trigger. It supplies no route, target or waypoint:

```bash
rosrun ruins_urban_01 launch_e2_b1_trial.py \
  --overlay-file /tmp/fuel_building_baseline_overlay/fuel_e2_primary_damaged_interior_baseline.launch \
  --output-dir "$HOME/uav_experiment_results/B1_E2_height_gate_01"
```

Before it starts anything, the command checks ROS for stale FUEL nodes with
names that would collide with this trial. If it reports
`existing_fuel_session`, stop only the listed stale nodes and rerun the same
command. A missing ROS master is valid: `roslaunch` will create one. The
trigger process exits after publishing the current-pose start signal by
design. Let the enclosing launch continue until FUEL reports `finish
exploration.` and the recorder writes the final online map. The first run is a
height-contract gate, not one of the five formal repetitions. Only after its
trajectory-height audit passes should the launcher be repeated with the five
formal output suffixes:

```text
$HOME/uav_experiment_results/B1_E2_rep01
$HOME/uav_experiment_results/B1_E2_rep02
$HOME/uav_experiment_results/B1_E2_rep03
$HOME/uav_experiment_results/B1_E2_rep04
$HOME/uav_experiment_results/B1_E2_rep05
```

Do not run two repetitions concurrently. Do not add RViz navigation goals.

The recorder is read-only.  It records a `planner_stall` failure only after
FUEL has published at least one B-spline and then, for 45 s, publishes no new
B-spline while the odometry displacement remains below 0.05 m. This rule does
not intervene in FUEL; it prevents a failed attempt from waiting until the
global recorder timeout. Apply the same rule to all B1 repetitions and report
the resulting success rate.

## Offline Evaluation and Archiving

After each completed run, evaluate the map against the E2 interior reference:

```bash
RUN=~/uav_experiment_results/B1_E2_rep01
TRUTH=/tmp/coop_building_e2_primary/pcd/Coop-Building-E2-Primary-Damaged-Interior_interior_reference.pcd

rosrun ruins_urban_01 evaluate_surface_map.py \
  --truth-pcd "$TRUTH" \
  --observed-pcd "$RUN/final_online_occupancy.pcd" \
  --snapshots-csv "$RUN/snapshots.csv" \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --output "$RUN/map_quality.json"
```

Before accepting a run into the five-repetition table, verify that its recorded
trajectory obeyed the indoor altitude contract:

```bash
rosrun ruins_urban_01 validate_flight_envelope.py \
  --trajectory-csv "$RUN/trajectory.csv" \
  --min-z-m 0.80 \
  --max-z-m 2.05 \
  --tolerance-m 0.02 \
  --output "$RUN/flight_envelope.json"
```

The output must state `passed: true` and `violation_samples: 0`. A failed
height-contract check is retained as a failed trial; it is never replaced by a
new run without being recorded.

The launcher writes directly to `~/uav_experiment_results`, so no separate
copy from `/tmp` is required.

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
