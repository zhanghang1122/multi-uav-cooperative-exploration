# Single-UAV Independent Mapping Adapter

This ROS Noetic package adds an independent OctoMap reconstruction channel to
the official FUEL single-UAV Frontier-exploration baseline. It does not modify
FUEL, and it never publishes a goal, waypoint, trajectory, target coordinate,
or planner parameter.

## Purpose

FUEL remains responsible for online Frontier selection and autonomous motion.
This package consumes only FUEL's rendered depth image and matching sensor pose,
then publishes a sensor-frame point cloud and its dynamic transform for
`octomap_server`. The resulting OctoMap is independent from FUEL's planning
occupancy map and is intended for reconstruction evaluation.

## Dependencies

- ROS Noetic
- FUEL launched separately and already publishing `/pcl_render_node/depth` and
  `/pcl_render_node/sensor_pose`
- `octomap_server`

## Generate the FUEL Overlay

The helper below copies only FUEL launch XML into `/tmp`; it leaves the FUEL
checkout untouched. The full ruins PCD is supplied only to FUEL's local sensor
renderer. The planner receives no obstacle map, route, waypoint sequence, or
target coordinate.

```bash
rosrun ruins_single_uav_exploration prepare_fuel_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --variant base \
  --output-dir /tmp/ruins_fuel_overlay/base
```

## Start

Build and source the workspace containing this repository, then start FUEL's
normal autonomous exploration launch. In a second terminal, run:

```bash
roslaunch ruins_single_uav_exploration fuel_global_mapping.launch
```

If the FUEL launch is waiting for its standard start message, use this third
terminal command. It publishes the current measured pose, so it starts
Frontier exploration without providing a destination or route:

```bash
roslaunch ruins_single_uav_exploration automatic_trigger.launch
```

The map is published by `octomap_server` on its standard topics, including
`/octomap_point_cloud_centers` and `/octomap_binary`.

For a read-only visualization of the independent map, run:

```bash
roslaunch ruins_single_uav_exploration view_global_mapping.launch
```

The RViz configuration uses `map` as its fixed frame and displays only the
independent OctoMap occupied centers. It has no interactive goal tool and
publishes no planning or control message.

## Record a Formal Single-UAV Baseline Trial

After the FUEL exploration process and the independent mapping launch are
running, start this recorder in a separate terminal before sending FUEL's
position-neutral start signal:

```bash
roslaunch ruins_single_uav_exploration record_single_uav_trial.launch \
  output_dir:=/tmp/ruins_trials/B1_base_run01 \
  scene_variant:=base \
  max_duration_s:=1800
```

It observes only `/state_ukf/odom`, `/planning/bspline`, `/rosout_agg`, and
the independent `/octomap_point_cloud_centers`. When FUEL reports `finish
exploration.`, it saves these evidence files:

- `trajectory.csv`: time-stamped measured vehicle trajectory;
- `map_growth.csv`: independent occupied-voxel count over time;
- `snapshots/`: periodic independent-map snapshots for an offline quality curve;
- `final_independent_octomap.pcd`: final reconstruction from OctoMap only;
- `trial_summary.json`: completion status, duration, path length, and run
  metadata that explicitly records the absence of route, waypoint, and online
  truth-map priors.

The ground-truth ruins PCD is deliberately not an input to this node. It is
used only later, offline, to calculate map Precision, Recall, and F1.

## Offline Map Quality Evaluation

After a completed trial, run the evaluator with the scene truth PCD. This is
an offline comparison only; it cannot affect FUEL's behavior during the run.

```bash
rosrun ruins_single_uav_exploration evaluate_independent_map.py \
  --truth-pcd "$(rospack find ruins_urban_01)/maps/pcd/Ruins-Urban-01_base.pcd" \
  --observed-pcd /tmp/ruins_trials/B1_base_run01/final_independent_octomap.pcd \
  --snapshot-dir /tmp/ruins_trials/B1_base_run01/snapshots \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --output /tmp/ruins_trials/B1_base_run01/map_quality.json
```

The evaluator reports voxel-surface Precision, Recall, and F1 and writes a
time-indexed snapshot quality curve when snapshots are present. The spatial
resolution and tolerance are explicit run parameters and must remain identical
across methods in a paper comparison.

## Verification

Before treating a run as an experiment, verify all of the following during one
autonomous FUEL run:

1. `/ruins_global_mapping/depth_cloud_sensor` contains clouds in the camera frame;
2. TF resolves `map` to that camera frame at the cloud timestamp;
3. `/octomap_point_cloud_centers` grows while the vehicle explores;
4. no node in this package publishes to FUEL planning or control topics.

The repository test covers depth-image decoding and camera-frame projection.
