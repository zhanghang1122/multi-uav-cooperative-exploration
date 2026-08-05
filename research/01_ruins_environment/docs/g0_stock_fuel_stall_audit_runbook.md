# G0 Runbook: Stock-FUEL Reachability/Stall Audit

## Purpose

G0 is **one diagnostic run**, not a five-run experiment and not a paper result.
It captures whether stock FUEL completes, reports no coverable Frontier, or
stalls after issuing no new trajectory and making no odometry progress. It does
not alter FUEL source, planner parameters, map geometry, target coordinates or
routes.

The required outputs are:

- `launch_request.json`: guarded launcher accepted the run;
- `recorder_startup.json`: the recorder actually initialized;
- `trial_summary.json`: completion/stall/timeout status;
- `runtime_diagnostics.json`: recent relevant FUEL log evidence;
- `trajectory.csv`, map snapshots and `final_online_occupancy.pcd`.

Do not run B1 repeats, B2, B3 or P until these files exist and are reviewed.

## Clean Start

Open a terminal in the Ubuntu VM and use the project checkout on the candidate
branch. Close all prior FUEL/Gazebo/RViz sessions first. `rosnode list` must
show only `/rosout` before starting this run. A running `roscore` is expected.

```bash
cd ~/catkin_ws/src/multi-uav-cooperative-exploration
git switch scene-environment-candidates
git pull --ff-only origin scene-environment-candidates

cd ~/catkin_ws
catkin_make -j2

source /opt/ros/noetic/setup.bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash

rosnode list
```

If any node other than `/rosout` is listed, do not start another trial. Close
the old run first; otherwise two FUEL sessions can share node names and corrupt
the evidence.

## Generate the Fixed E2 Assets

```bash
rosrun ruins_urban_01 generate_e2_primary_benchmark.py \
  --output-dir /tmp/coop_building_e2_primary

rosrun ruins_urban_01 prepare_fuel_baseline_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --assets-dir /tmp/coop_building_e2_primary \
  --scene e2_primary_damaged_interior \
  --output-dir /tmp/fuel_building_baseline_overlay
```

These commands create the simulation assets and a temporary FUEL overlay. They
do not give FUEL the reference PCD as a planning prior; its sensor simulation
uses the PCD, while map truth is reserved for offline evaluation.

## Start Exactly One G0 Trial

```bash
mkdir -p ~/uav_experiment_results

rosrun ruins_urban_01 launch_e2_b1_trial.py \
  --overlay-file /tmp/fuel_building_baseline_overlay/fuel_e2_primary_damaged_interior_baseline.launch \
  --output-dir "$HOME/uav_experiment_results/G0_B1_E2_stock_01" \
  --planner-stall-timeout-s 45
```

The launcher starts the overlay, fixed RViz view, read-only recorder and a
position-neutral trigger. Do not publish a goal, click a navigation point or
start a second trigger. RViz is presentation-only and does not affect planner
input.

The recorder is marked as a required launch node. If it fails to initialize,
the complete G0 launch stops rather than leaving an unrecorded FUEL simulator
running. A valid run directory therefore contains `recorder_startup.json`.

## Review the Result

After the launcher exits, inspect only the saved files:

```bash
RUN="$HOME/uav_experiment_results/G0_B1_E2_stock_01"
ls -lh "$RUN"
cat "$RUN/recorder_startup.json"
cat "$RUN/trial_summary.json"
cat "$RUN/runtime_diagnostics.json"
```

Interpretation:

- `stop_reason: fuel_reported_finish`: stock B1 finished according to FUEL;
  G1 still needs an explicit infeasible-candidate test before any cooperative
  method begins.
- `stop_reason: planner_stall`: this is the expected evidence for the stated
  failure mode. Preserve the directory unchanged. The next task is G1, not a
  rerun with modified geometry.
- `stop_reason: timeout` or missing outputs: this is an integration failure;
  repair the launcher/recorder before discussing algorithm quality.

The source PCD and evaluation script must not be run during G0. Map-quality
evaluation begins only after G1 confirms that candidate infeasibility is
handled rather than hidden by a timeout.
