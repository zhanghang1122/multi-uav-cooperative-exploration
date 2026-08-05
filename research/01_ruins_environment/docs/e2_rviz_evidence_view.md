# E2 RViz Evidence View

`fuel_b1_rviz.launch` is the fixed presentation-only RViz view for E2.  It
does not publish a route, target, map or planning parameter.

| Visual item | Source | Meaning |
| --- | --- | --- |
| Cyan surface | `/sdf_map/occupancy_all`, filtered for display | Online observed floor/low surfaces. |
| Magenta surface | `/sdf_map/occupancy_all`, filtered for display | Online observed walls and obstacles. |
| Red arrow and sphere | `/state_ukf/odom`, display marker | Current simulator pose and heading. |
| Dark-blue line | `/state_ukf/odom`, display marker | Executed trajectory accumulated during the current RViz session. |

The display helper clips points at `z >= 2.30 m` and voxel-centres its
presentation copy at `0.15 m`.  This removes the simulator map's upper-bound
layer from the **display only** and makes flat walls appear continuous.  The
raw FUEL map, recorder input, planner map and offline evaluator are unchanged.

The view intentionally does not render a truth mesh or truth PCD.  It remains
valid for a live recording because every displayed surface is an online
observation.
