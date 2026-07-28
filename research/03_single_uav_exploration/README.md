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

## Verification

Before treating a run as an experiment, verify all of the following during one
autonomous FUEL run:

1. `/ruins_global_mapping/depth_cloud_sensor` contains clouds in the camera frame;
2. TF resolves `map` to that camera frame at the cloud timestamp;
3. `/octomap_point_cloud_centers` grows while the vehicle explores;
4. no node in this package publishes to FUEL planning or control topics.

The repository test covers depth-image decoding and camera-frame projection.
