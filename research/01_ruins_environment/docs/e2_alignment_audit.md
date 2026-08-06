# E2 Map Alignment Audit

This audit answers one narrow question: is a low map Recall primarily caused
by one rigid translation or rotation between the recorded occupancy map and
the offline truth PCD?

It is diagnostic only. The unregistered score remains the official score.
The estimated transform is never sent to FUEL, ROS, the map, or the planner.

## Runtime frame evidence

Recorder schema 4 stores the first observed ROS frame names and timestamp
ranges under `recorded_frames` in `trial_summary.json`. Frame names alone do
not prove numerical alignment, but their absence must no longer be hidden.

For an already running legacy recorder, inspect the live headers:

```bash
rostopic echo -n 1 /sdf_map/occupancy_all/header
rostopic echo -n 1 /state_ukf/odom/header
```

## Offline diagnostic for the current E2 gate

```bash
RUN=$HOME/uav_experiment_results/G0_E2_virtual_ceiling_gate_01
TRUTH=/tmp/coop_building_e2_primary/pcd/Coop-Building-E2-Primary-Damaged-Interior_interior_reference.pcd

rosrun ruins_urban_01 audit_surface_alignment.py \
  --truth-pcd "$TRUTH" \
  --observed-pcd "$RUN/final_online_occupancy.pcd" \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --virtual-ceiling-z-m 1.85 \
  --max-correspondence-m 0.3 \
  --output "$RUN/alignment_audit.json"

python3 -m json.tool "$RUN/alignment_audit.json"
```

## Decision rule

Rigid frame mismatch is supported only when all of the following occur:

1. direct surface Precision is below 0.95;
2. diagnostic registration increases Recall by more than 0.02;
3. the estimated correction exceeds 0.10 m translation or 1 degree rotation.

A near-identity transform and negligible Recall gain reject rigid frame
misalignment. They do not prove that all truth surfaces are observable and do
not prove that exploration is complete.

For the previously recorded E2 gate, direct Precision was 0.999328 while
Recall was 0.124004. Before ICP is run, that pattern already provides strong
evidence for missing coverage rather than a global rigid offset.
