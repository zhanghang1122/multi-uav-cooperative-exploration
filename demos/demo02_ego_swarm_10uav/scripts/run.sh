#!/usr/bin/env bash
set -euo pipefail

workspace="${EGO_SWARM_WS:-$HOME/uav_ego_planner_demo/ego-planner-swarm}"
launch_root="${EGO_SWARM_LAUNCH_ROOT:-$HOME/uav_ego_planner_demo/manual_launch}"
launch_file="${launch_root}/manual_simple_run.launch"

test -f "${workspace}/devel/setup.bash" || {
  echo "Missing built workspace: ${workspace}" >&2
  exit 1
}
test -f "${launch_file}" || {
  echo "Missing generated launch file: ${launch_file}" >&2
  exit 1
}

source /opt/ros/noetic/setup.bash
source "${workspace}/devel/setup.bash"
roslaunch "${launch_file}"

