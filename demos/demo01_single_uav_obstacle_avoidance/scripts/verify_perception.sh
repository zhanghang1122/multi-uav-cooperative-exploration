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
  timeout 8 rostopic echo -n 1 "${topic}/header" >/dev/null
done

echo "=== point-cloud rate"
set +e
timeout 8 rostopic hz /uav1/camera/depth/color/points
rate_status=$?
set -e
if [[ ${rate_status} -ne 0 && ${rate_status} -ne 124 ]]; then
  exit "${rate_status}"
fi

echo "=== point-cloud header"
timeout 8 rostopic echo -n 1 /uav1/camera/depth/color/points/header

echo "Perception checks completed. Inspect the reported frame before mapping."
