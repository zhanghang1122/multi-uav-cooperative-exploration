# Platform Calibration Before Environment Generation

The scene dimensions must follow the simulated aircraft actually used in the
experiment.  Do not copy a corridor width from an unrelated paper or select it
by appearance in Gazebo.

The collector is passive. It records the interface used by the selected stack
while MARSIM or FUEL is already running. It never sends a goal, trajectory,
map, or flight-control command. Run the interface audit first;
vehicle dimensions are deliberately a separate step.

## 1. Record the platform profile

First collect the runtime interfaces without any vehicle-size estimate:

```bash
rosrun ruins_urban_01 collect_platform_profile.py \
  --sensor-stack marsim-os128 \
  --output /tmp/ruins_platform_interface.json
```

`marsim-os128` records `/quad_0/lidar_slam/odom` and
`/quad0_pcl_render_node/sensor_cloud` by default. The FUEL depth-camera stack
is separate and must be requested explicitly with `--sensor-stack fuel-depth`.
Do not launch MARSIM and then audit the unrelated FUEL depth topics.

The result must report `passed: true`. It is not yet usable for scene geometry.

Then obtain the collision diameter from the active simulated model and select
a per-side clearance margin. The effective planning diameter is

```text
D_eff = collision_diameter + 2 * safety_margin
```

Repeat the collection with those measured values. Example only (replace the
two vehicle values by values measured from the active model):

```bash
rosrun ruins_urban_01 collect_platform_profile.py \
  --collision-diameter-m 0.65 \
  --safety-margin-m 0.10 \
  --output /tmp/ruins_platform_profile.json
```

A mismatch between world/map odometry and sensor-pose frames is a real
interface issue and must be resolved before mapping or scene generation begins.

## 2. Derive the geometry constraints

```bash
rosrun ruins_urban_01 derive_geometry_constraints.py \
  --platform-profile /tmp/ruins_platform_profile.json \
  --output /tmp/ruins_geometry_constraints.json
```

The derived constraints use `D_eff`, rather than fixed metres, for normal
corridors, bottlenecks, observation zones, low-clearance structures, and
minimum obstacle gaps.  They are offline generator/validation inputs, not
online planner inputs.

## 3. Literature role

The protocol follows the closed-loop unknown-map requirement of Ren et al.
in *Chinese Journal of Aeronautics* (2021, doi:10.1016/j.cja.2020.12.018), the
GPS-denied navigation architecture of Wang et al. in *Aerospace Science and
Technology* (2022, doi:10.1016/j.ast.2022.107521), and the separation of
cooperative allocation from local planning described in the relevant
*Aerospace Science and Technology* multi-UAV studies.
