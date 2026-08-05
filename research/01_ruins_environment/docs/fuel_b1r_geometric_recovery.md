# B1-R: Reachable-Frontier Recovery

## Purpose

B1-R is a single-UAV recovery comparison, not the proposed multi-UAV method.
It starts from stock FUEL's online frontier system. It addresses the observed
E2 failure: FUEL repeatedly selected a current online viewpoint for which its
geometric A* search reported `No path to next viewpoint`. The stock function
returns `FAIL` at that point, and the state machine can select the same
infeasible candidate again in `PLAN_TRAJ`.

The recovery rule is deliberately narrow:

1. FUEL keeps its online map, frontier detection, viewpoint generation,
   global tour, and local refinement unchanged.
2. When the tour-selected viewpoint has no geometric A* path, B1-R evaluates
   the remaining viewpoints generated from that *same current online frontier
   set* and selects the collision-free path with the smallest geometric length.
   It does not create a new target or retain a scene-specific route.
3. If a geometric path succeeds but the subsequent mid-range kinodynamic seed
   fails, B1-R takes a 2.5 m prefix of that path and invokes FUEL's existing
   `planExploreTraj` generator. This follows FUEL's own far-goal local-horizon
   pattern instead of optimizing a long path through an unseen corner.
4. No route, target coordinate, room label, truth map, or manual intervention
   is supplied.

This is a current-map reachability fallback, not a preplanned route and not
an obstacle bypass. A candidate rejected in one planning cycle can be
reconsidered only if FUEL reconstructs it from a changed online map later.

## Basis

FUEL uses a hierarchical exploration procedure: frontier information, global
coverage ordering, local viewpoint refinement, then safe trajectory
generation. In the verified source, a selected viewpoint is passed to a
geometric A* search. The E2 run demonstrated that a failed search returns
`FAIL` directly; it does not advance to another current-cycle candidate.

The B1-R patch checks current-cycle candidate reachability at exactly that
failure point, then applies the local geometric-path trajectory generation
already present in FUEL's verified far-goal branch to a documented mid-range
dynamic-feasibility failure.
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

First run one verification trial. Do not start five repeats until its output
contains either `fuel_reported_finish` or a clearly classified new failure.
Use the recorder as follows so the summary is correctly labeled and fallback
events are counted:

```bash
rosrun ruins_urban_01 record_fuel_b1_trial.py \
  --scene e2_primary_damaged_interior \
  --method-id B1R_fuel_reachable_frontier_recovery \
  --recovery-log-token "B1-R" \
  --output-dir ~/uav_experiment_results/B1R_E2_rep01 \
  --planner-stall-timeout-s 45 \
  --stall-motion-threshold-m 0.05
```

Report `recovery_events`, success rate, map Precision/Recall/F1,
T80/T90/T95, completion time, and path length. B1 remains an unmodified
reference; B1-R is a recovery ablation that will become one component of the
later B3/P multi-UAV system.
