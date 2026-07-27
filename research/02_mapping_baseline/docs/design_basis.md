# Design Basis and Upstream Interfaces

## MARSIM

F. Kong et al., "MARSIM: A Light-Weight Point-Realistic Simulator for
LiDAR-Based UAVs," IEEE Robotics and Automation Letters, vol. 8, no. 5,
pp. 2954-2961, 2023. DOI: 10.1109/LRA.2023.3264163.

Primary sources:

- paper: https://arxiv.org/abs/2211.10716
- code: https://github.com/hku-mars/MARSIM/tree/ubuntu20
- official single-UAV wiring:
  `test_interface/launch/single_drone.xml`
- CPU renderer:
  `local_sensing/src/pointcloud_render_node.cpp`

The official renderer publishes two local-cloud forms:

- `cloud`: local returns expressed in `world`, intended for visualization and
  world-frame consumers;
- `sensor_cloud`: the same local measurement expressed in `sensor`, accompanied
  by MARSIM's `world -> sensor` transform.

This baseline uses `sensor_cloud`. OctoMap derives the LiDAR ray origin from the
input frame transform. Feeding the world-coordinate visualization cloud would
make the input frame insufficient to identify the moving sensor origin.

## OctoMap

A. Hornung, K. M. Wurm, M. Bennewitz, C. Stachniss, and W. Burgard,
"OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees,"
Autonomous Robots, vol. 34, pp. 189-206, 2013.
DOI: 10.1007/s10514-012-9321-0.

Primary sources:

- project: https://octomap.github.io/
- ROS mapping stack: https://github.com/OctoMap/octomap_mapping

OctoMap is selected for the baseline because it explicitly represents occupied,
free, and unknown 3D space. The later frontier stage requires this distinction.
The baseline does not claim OctoMap as a paper contribution.

## Scope

Ground-truth odometry is used in Stage 02. This isolates mapping behavior from
SLAM drift and is consistent with a controlled algorithm-development baseline.
State estimation may be introduced later as a separate robustness condition,
but it must not be conflated with the mapping result reported here.
