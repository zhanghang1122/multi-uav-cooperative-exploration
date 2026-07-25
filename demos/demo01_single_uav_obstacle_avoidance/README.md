# Demo 01: Single-UAV Obstacle Avoidance

## Status

The objective of this exercise was a complete Prometheus/PX4 single-UAV
obstacle-avoidance loop. The historical run did not complete that objective.
Only the D435i perception stage below is accepted as verified.

## Verified Scope

This archive keeps only the verified part of the earlier Prometheus exercise:

```text
Gazebo obstacle
  -> simulated Intel RealSense D435i
  -> color and depth images
  -> /uav1/camera/depth/color/points
  -> RViz visualization
```

Recorded evidence showed the point cloud publishing at approximately 14 Hz and
a manually inserted Gazebo box appearing in the color, depth, and point-cloud
views.

## Not Claimed

The later OctoMap/EGO-Planner flight attempt is not included as a successful
demo. Its final recorded failure was a bad transform: the point cloud used
`uav1/d435i_link`, while the transform placed that frame near `z = 0` when the
aircraft was near `z = 1.49 m`. The planner consequently treated the vehicle as
being inside an obstacle.

The temporary runtime TF broadcaster and the unverified flight scripts are
intentionally omitted.

## Environment

- Ubuntu 20.04
- ROS Noetic
- Gazebo Classic
- Prometheus P230 model
- PX4 SITL and MAVROS
- simulated D435i

## Verification

After launching the Prometheus P230+D435i simulation, run:

```bash
bash demos/demo01_single_uav_obstacle_avoidance/scripts/verify_perception.sh
```

Pass criteria:

- all required topics have publishers;
- the point cloud produces a non-zero rate;
- the point-cloud frame is printed for TF inspection.

The screenshots in `evidence/` are retained as historical evidence, not as a
substitute for a repeatable runtime test.

## Why There Is No Avoidance Run Script

A runnable avoidance wrapper would imply that the full chain is known to work.
The final recorded run did not meet that condition:

```text
Gazebo + PX4 + D435i
  -> point cloud verified
  -> OctoMap/EGO input
  -> incorrect world-to-D435i transform
  -> planner reported the vehicle inside an obstacle
  -> no successful avoidance flight was recorded
```

The earlier temporary TF broadcaster is excluded because it was proposed as a
diagnostic fix but never followed by a confirmed successful flight. This demo
may be upgraded to `verified` only after an Ubuntu rerun records:

1. correct vehicle and D435i transforms throughout takeoff;
2. an obstacle in the planner's collision map;
3. a collision-free trajectory around that obstacle;
4. arrival at the commanded goal;
5. repeatability across at least three clean launches.
