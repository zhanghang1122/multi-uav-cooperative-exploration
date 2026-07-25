#!/usr/bin/env bash
set -euo pipefail

workspace="${FUEL_WS:-$HOME/fuel_ws}"
test -f "${workspace}/devel/setup.bash" || {
  echo "Missing built FUEL workspace: ${workspace}" >&2
  exit 1
}

source /opt/ros/noetic/setup.bash
source "${workspace}/devel/setup.bash"
roslaunch exploration_manager exploration.launch

