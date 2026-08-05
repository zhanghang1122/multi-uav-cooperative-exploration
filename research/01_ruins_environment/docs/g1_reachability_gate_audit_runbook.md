# G1 Reachability-Gate Audit

## Purpose

G0 showed that stock FUEL can emit `finish exploration.` while that event alone
does not prove map completeness.  G1 is the next **single-run component gate**
from Protocol V2.1, not a new five-run experiment.  It tests the minimum
contract required before R can be integrated with allocation: an observed
obstacle candidate is rejected and a separate locally clearance-checked
candidate is selected using the same live occupancy observation.  This local
check is not a claim that all unobserved cells are free.

This follows the safe/reachable-frontier condition described by Senarathne and
Wang, *Robotics and Autonomous Systems* (2015),
https://doi.org/10.1016/j.robot.2015.05.009.  The script is intentionally
read-only and does not claim that stock FUEL has been modified.

## Preconditions

1. Start one clean E2 FUEL session through the existing guarded launcher.
2. Wait until the online map and odometry are visible.
3. In another terminal with the same ROS environment, run:

```bash
rosrun ruins_urban_01 g1_reachability_gate_audit.py \
  --output "$HOME/uav_experiment_results/G1_E2_reachability_gate_01.json"
```

The command subscribes only to `/sdf_map/occupancy_all` and
`/state_ukf/odom`.  It exits automatically after writing the report.

## Acceptance Rule

The report is accepted only when all statements below hold:

- `passed` is `true`;
- `audit_observed_obstacle` is `rejected`;
- `audit_local_clear_candidate` is `eligible_selected`;
- `truth_map_usage` is `none` and `route_or_goal_prior_used` is `false`.

This result permits the next engineering step: integrate the same R decision
states into the B1-R candidate lifecycle.  It does **not** validate global
frontier allocation, autonomous completion, or three-UAV collaboration.
