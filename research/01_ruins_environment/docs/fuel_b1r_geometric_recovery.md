# B1-R: FUEL Geometric-Path Recovery

## Purpose

B1-R is a single-UAV recovery comparison, not the proposed multi-UAV method.
It starts from the unchanged FUEL Frontier system used in B1. It addresses one
observed failure mode in E2: FUEL can successfully find a geometric A* path
to an online-selected viewpoint, then fail when its mid-range kinodynamic A*
seed search is unable to produce a trajectory. Stock FUEL remains in
`PLAN_TRAJ` and repeats that failure.

The recovery rule is deliberately narrow:

1. FUEL keeps its online map, frontier detection, viewpoint generation,
   global tour, and local refinement unchanged.
2. The stock geometric A* path to the selected online viewpoint must already
   have succeeded.
3. Only when the subsequent mid-range kinodynamic search fails, B1-R invokes
   FUEL's existing `planExploreTraj` generator on that already verified path.
4. No route, target coordinate, room label, truth map, or manual intervention
   is supplied.

This is a fallback for a dynamic-feasibility failure, not a preplanned route
and not an obstacle bypass.

## Basis

FUEL uses a hierarchical exploration procedure: frontier information,
global coverage ordering, local viewpoint refinement, then safe trajectory
generation. Its implementation first validates a geometric A* path to the
selected viewpoint. For near and far path lengths it already creates a
trajectory from that path; only the mid-range branch requires a kinodynamic
search and returns failure when it cannot generate a seed.

The B1-R patch applies the same geometric-path trajectory generation already
present in the verified FUEL branches to this documented mid-range failure.
It is consistent with frontier-exploration work that validates and maintains
reachable sensing targets, rather than repeatedly commanding an infeasible
viewpoint.

References:

1. Zhou, B., Zhang, Y., Chen, X., and Shen, S. FUEL: Fast UAV Exploration
   Using Incremental Frontier Structure and Hierarchical Planning. IEEE
   Robotics and Automation Letters, 2021. DOI: 10.1109/LRA.2021.3051563.
2. Umari, H. and Mukhopadhyay, S. Incremental Algorithms for Safe and
   Reachable Frontier Detection for Robot Exploration. Robotics and
   Autonomous Systems, 2015. DOI: 10.1016/j.robot.2015.08.004.

## Applying the Reversible Patch

With the project workspace sourced, validate the exact FUEL source block:

```bash
rosrun ruins_urban_01 apply_fuel_geometric_recovery.py \
  --fuel-workspace ~/fuel_ws \
  --dry-run
```

Then apply it and rebuild only the FUEL workspace:

```bash
rosrun ruins_urban_01 apply_fuel_geometric_recovery.py \
  --fuel-workspace ~/fuel_ws

cd ~/fuel_ws
catkin_make -j2
```

The tool backs up the original source beside the modified file as
`fast_exploration_manager.cpp.b1r_original`, and creates
`~/fuel_ws/fuel_b1r_geometric_recovery_manifest.json`. The manifest records
the source path, backup path, before/after checksums, and the no-prior runtime
contract.

Restore stock FUEL B1 when required:

```bash
rosrun ruins_urban_01 apply_fuel_geometric_recovery.py \
  --fuel-workspace ~/fuel_ws \
  --restore

cd ~/fuel_ws
catkin_make -j2
```

## Experimental Role

Use the same E2 scene, sensor settings, evaluation reference, recorder
intervals, and five-repeat protocol as B1. Use the recorder as follows so the
summary is correctly labeled and the precise fallback is counted:

```bash
rosrun ruins_urban_01 record_fuel_b1_trial.py \
  --scene e2_primary_damaged_interior \
  --method-id B1R_fuel_geometric_path_recovery \
  --recovery-log-token "B1-R recovery:" \
  --output-dir ~/uav_experiment_results/B1R_E2_rep01 \
  --planner-stall-timeout-s 45 \
  --stall-motion-threshold-m 0.05
```

Report `recovery_events`, success rate, map Precision/Recall/F1,
T80/T90/T95, completion time, and path length. B1 remains an unmodified
reference; B1-R is a recovery ablation that will become one component of the
later B3/P multi-UAV system.
