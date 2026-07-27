# Stage 02 Summary: Online 3D Mapping Baseline

## Purpose

This stage isolates the perception-to-map chain before autonomous planning is
introduced. The full PCD map is treated as simulator truth. MARSIM renders a
bounded local LiDAR observation from the current UAV pose, and OctoMap fuses
only those observations into an incrementally growing probabilistic occupancy
map.

## Design Decisions

1. MARSIM is used instead of Gazebo for LiDAR rendering because it consumes PCD
   maps directly and is designed for lightweight LiDAR-based UAV simulation.
2. The CPU renderer is the default because the target platform is an Ubuntu
   virtual machine.
3. OctoMap supplies explicit occupied, free, and unknown 3D states needed by
   later frontier extraction.
4. A local-cloud gate gives the mapper one auditable input topic and rejects
   unexpected coordinate frames.
5. Stage 02 does not command motion; it validates the sensing-to-map chain at
   the initial pose and cannot be presented as an exploration result.
6. A lightweight UAV marker and measured odometry path make vehicle motion
   explicit in RViz without requiring an external mesh resource.
7. The truth cloud is not displayed in the default RViz configuration.

## Implemented Interface

```text
/map_generator/global_cloud
  simulator truth only

/quad0_pcl_render_node/sensor_cloud
  MARSIM local LiDAR measurement in the sensor frame

/mapping/input_cloud
  sole OctoMap input after frame validation

/octomap_binary
  probabilistic 3D occupancy map

/octomap_point_cloud_centers
  occupied voxel centers for visualization and growth checks

/ruins/uav0_markers
  current UAV body marker driven by the sensor transform

/ruins/uav0_path
  measured path accumulated from odometry
```

## Paper Relevance

The stage is methodological infrastructure rather than the paper's algorithmic
contribution. Its role is to establish that:

- the environment is initially unknown to the mapping algorithm;
- observations are local and pose-dependent;
- the 3D map grows online;
- occupied, free, and unknown space can support later frontier detection;
- fixed sensor and map parameters can be reused by every comparison method.

## Current Evidence Status

The repository structure, Python syntax, XML syntax, PCD format, and topic
wiring can be checked on the Windows host. Actual ROS messages, local map
updates, and virtual-machine performance require an Ubuntu 20.04 runtime trial.
Until the generated JSON report passes, this stage is
`implementation_ready_runtime_pending`, not experimentally complete.

## Next Stage Gate

Stage 03 may begin only after all three fixed variants pass this interface
check. Stage 03 performs online frontier detection, viewpoint selection, and
collision-free single-UAV planning without any predefined motion.
