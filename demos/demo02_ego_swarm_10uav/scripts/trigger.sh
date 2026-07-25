#!/usr/bin/env bash
set -euo pipefail

workspace="${EGO_SWARM_WS:-$HOME/uav_ego_planner_demo/ego-planner-swarm}"
source /opt/ros/noetic/setup.bash
source "${workspace}/devel/setup.bash"

timeout 5 rostopic pub -r 2 /traj_start_trigger geometry_msgs/PoseStamped \
  "{header: {frame_id: 'world'}, pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}"

