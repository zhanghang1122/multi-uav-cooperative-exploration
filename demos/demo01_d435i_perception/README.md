# Demo 01: D435i Perception Baseline

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
bash demos/demo01_d435i_perception/scripts/verify_perception.sh
```

Pass criteria:

- all required topics have publishers;
- the point cloud produces a non-zero rate;
- the point-cloud frame is printed for TF inspection.

The screenshots in `evidence/` are retained as historical evidence, not as a
substitute for a repeatable runtime test.

