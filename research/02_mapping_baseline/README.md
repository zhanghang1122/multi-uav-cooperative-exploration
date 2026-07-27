# 02. Online 3D Mapping Baseline

This ROS package connects the Ruins-Urban-01 PCD truth map to the official
MARSIM Ubuntu 20.04 interface and incrementally builds an OctoMap from simulated
local LiDAR measurements.

The package name is `ruins_mapping_baseline`.

## Scientific Boundary

MARSIM's `/map_generator/global_cloud` is simulator truth. It is used only by
the LiDAR renderer. The mapper receives `/mapping/input_cloud`, which is
forwarded exclusively from `/quad0_pcl_render_node/sensor_cloud`.

MARSIM also publishes `/quad0_pcl_render_node/cloud` with points already
expressed in `world`. That topic is useful for visualization but is not used by
OctoMap: the sensor-frame cloud and MARSIM's `world -> sensor` transform are
required for the correct ray origin and free-space update.

The included short waypoint route validates sensing and mapping. It is declared
reference motion and is not an autonomous exploration algorithm. An incomplete
map is expected from this route; complete coverage belongs to the online
frontier/FUEL stage.

## Data Flow

```text
Ruins PCD truth
  -> MARSIM map_generator
  -> local MARSIM LiDAR cloud
  -> local_cloud_gate
  -> octomap_server
  -> online occupied/free/unknown map
```

## Supported Baseline

- Ubuntu 20.04 and ROS Noetic;
- official `hku-mars/MARSIM` `ubuntu20` branch;
- MARSIM CPU renderer by default;
- Livox Mid-360-style 360-degree simulated LiDAR;
- OctoMap resolution: 0.18 m;
- one simulated UAV and one shared world frame;
- fixed `base`, `medium`, or `complex` Ruins-Urban-01 map;
- RViz UAV body marker and measured odometry path.

## Quick Start

Complete the installation in
[`docs/ubuntu20_setup.md`](docs/ubuntu20_setup.md), then open terminal 1:

```bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_mapping_baseline mapping_baseline.launch \
  variant:=base \
  start_reference_trajectory:=false
```

Verify that RViz shows an orange local cloud, a height-colored online occupied
map, the `UAV0` marker, and its cyan measured path.
The complete truth cloud is intentionally absent from this RViz configuration.
The orange display subscribes to `/mapping/input_cloud`, which is the validated
MARSIM local measurement with its `"/sensor"` frame normalized to `sensor` for
ROS Noetic tf2 compatibility.

Open terminal 2:

```bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_mapping_baseline runtime_validation.launch duration_s:=90
```

Open terminal 3:

```bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_mapping_baseline reference_trajectory.launch
```

The reports are written to:

```text
/tmp/ruins_mapping_runtime.json
/tmp/ruins_mapping_trajectory.json
```

Only after `base` passes should `variant:=medium` and `variant:=complex` be
tested.

## PCD Inspection

```bash
rosrun ruins_mapping_baseline inspect_pcd.py \
  $(rospack find ruins_urban_01)/maps/pcd/Ruins-Urban-01_complex.pcd
```

The inspector verifies the declared point count and reports measured XYZ
bounds without publishing the truth map to any mapping node.

## Acceptance

The stage passes only when:

1. odometry and local LiDAR clouds are published;
2. the local-cloud gate forwards nonempty clouds in frame `sensor`;
3. OctoMap outputs appear and occupied cells grow as the UAV moves;
4. `/mapping/input_cloud` remains different from the truth topic;
5. the reference route finishes without timeout;
6. the UAV marker and measured path are visible in RViz;
7. the test is repeated on `base`, `medium`, and `complex`;
8. screenshots, OctoMap, and JSON reports are copied into a dated experiment
   directory.

Map completeness is deliberately not an acceptance condition here. It becomes
an acceptance condition only after the fixed route is replaced by online
frontier/FUEL exploration.

Runtime evidence from Ubuntu is still required. Static repository validation
does not claim that MARSIM ran successfully.
