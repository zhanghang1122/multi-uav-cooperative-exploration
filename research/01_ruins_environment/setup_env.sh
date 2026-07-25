#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GAZEBO_MODEL_PATH="${SCRIPT_DIR}/gazebo/models${GAZEBO_MODEL_PATH:+:${GAZEBO_MODEL_PATH}}"

echo "Ruins-Urban-01 is ready."
echo "Gazebo model path added: ${SCRIPT_DIR}/gazebo/models"
echo "Example:"
echo "  roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:=complex"
