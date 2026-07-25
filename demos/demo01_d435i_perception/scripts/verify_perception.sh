#!/usr/bin/env bash
set -euo pipefail

topics=(
  /uav1/camera/color/image_raw
  /uav1/camera/depth/image_raw
  /uav1/camera/depth/color/points
)

for topic in "${topics[@]}"; do
  echo "=== ${topic}"
  rostopic info "${topic}"
done

echo "=== point-cloud rate"
timeout 8 rostopic hz /uav1/camera/depth/color/points

echo "=== point-cloud header"
rostopic echo -n 1 /uav1/camera/depth/color/points/header

echo "Perception checks completed. Inspect the reported frame before mapping."

