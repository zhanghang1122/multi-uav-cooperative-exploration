# Protocol V2.1: Journal-Anchored Review and Execution Freeze

## 1. Decision

This document supersedes Protocol V2 for all **new** simulation work.  It
does not invalidate archived pilot folders, but it prevents them from being
reported as a comparison of cooperative algorithms.

The study remains:

> Three UAVs autonomously explore a fixed but runtime-unknown damaged-building
> interior, incrementally construct a shared 3D occupancy map, and improve
> mapping completeness and mission efficiency through reachability-aware
> frontier allocation and event-driven reassignment.

The reference PCD, room names, scene generator metadata and all evaluation
labels are offline-only.  They must never reach the planner, the allocation
module, the completion decision, or the run-time RViz layer.

## 2. What the Literature Supports, and What It Does Not

| Journal anchor | Mature idea used | Boundary for this study |
| --- | --- | --- |
| Zhou et al., *IEEE RA-L*, 2021, FUEL, DOI: 10.1109/LRA.2021.3051563 | Incremental frontier bookkeeping, hierarchical exploration and dynamically feasible trajectory generation form a defensible single-UAV baseline. | Stock FUEL is an external baseline, not evidence of multi-UAV coordination. |
| Senarathne and Wang, *Robotics and Autonomous Systems*, 2015, DOI: 10.1016/j.robot.2015.05.009 | A frontier must be safe and reachable before it is used as an exploration target. | A visible unknown boundary alone is never an allocatable task. |
| Bayer and Faigl, *Autonomous Robots*, 2026, DOI: 10.1007/s10514-025-10234-3 | Navigation and coordination should be separated; repeated trials should report time, distance, coverage and communication. | The initial three-UAV system uses a shared-map coordinator and distributed local execution, not an unsupported claim of fully decentralized SLAM. |
| Gao et al., *Automation in Construction*, 2023, DOI: 10.1016/j.autcon.2023.104753 | GPS-denied, cluttered indoor UAV reconstruction needs a clear localization, planning, collision-safety and reconstruction evaluation contract. | This paper assumes simulator odometry as pose input; it cannot claim a new or validated SLAM result. |
| Peng, *IET Cyber-Systems and Robotics*, 2024, DOI: 10.1049/csy2.12107 | Post-disaster exploration should be tested in constrained infrastructure scenes and assessed using mapping and safety evidence. | E2 is a measured damaged interior, not a decorative obstacle field. |
| Amigoni et al., *Autonomous Robots*, 2026, DOI: 10.1007/s10514-025-10221-8 | A planner's “no frontier” event and map completeness are different claims. | FUEL's finish message is recorded, but does not by itself prove complete exploration. |

The following claims are deliberately **out of scope**: new SLAM, semantic
recognition, victim search, reinforcement-learning control, radio-silent
gesture communication, map registration across independently drifting frames,
or robust real-world GPS-denied localization.

## 3. Corrected System Architecture

The previous pilot runs showed a real integration limitation: stock FUEL can
select a frontier whose local trajectory cannot be started and can remain in a
planning loop.  Calling this a cooperative result would be methodologically
incorrect.  The architecture is therefore frozen as four separate layers:

1. **Local mapping and motion layer**: each UAV consumes only its sensor data,
   pose estimate and motion limits, and maintains an inflated online map.
2. **Reachable-frontier service R**: clusters candidate frontiers, queries the
   same collision/motion feasibility contract used by the executor, and emits
   `eligible`, `rejected`, `covered`, `no-progress` or `invalidated` events.
3. **Team coordinator**: assigns only eligible frontier clusters and owns
   commitments, exclusion regions and reassignment events.  It shares online
   map/team state in one common simulation frame; it does not receive truth.
4. **Read-only evidence layer**: records maps, trajectories, events and
   metrics.  Paper-facing RViz renders only observed data, the UAV state,
   selected frontier and executed/planned trajectory.  It cannot alter any
   planning topic.

The fixed operational flight band is 0.80--2.05 m.  Wall tops remain outside
this band, so a UAV may not turn a room-navigation task into an invalid
over-the-wall shortcut.  Every door, corridor and branch is admitted only
after the **inflated planner map** reports a collision-free passage; a visual
gap in Gazebo is not sufficient evidence of reachability.

## 4. Fair Comparison Set

`R` is an engineering prerequisite, not an extra advantage awarded only to
the proposed method.  Once it passes the G1 gate below, every new multi-UAV
method uses the same local mapping, local navigation and R service.

| ID | Vehicles | Map/team information | Assignment rule | Role |
| --- | ---: | --- | --- | --- |
| G0-B1 | 1 | stock FUEL local state | stock FUEL | Diagnostic reproduction only; establishes the failure mode. |
| B1-R | 1 | one online map + R | local eligible-frontier selection | Single-UAV navigation substrate and ablation. |
| B2 | 3 | independent online maps; no map or target sharing | each UAV selects its own eligible frontier | Quantifies the effect of adding UAVs without cooperation. |
| B3 | 3 | shared online map, states and commitments | one-to-one minimum feasible route-cost assignment | Conventional cooperative baseline. |
| P | 3 | exactly B3 information | utility assignment plus event-driven reallocation | Proposed method. |

For P, a feasible pair `(i,j)` is scored by

```text
U(i,j) = w_g G(j) - w_c C(i,j) - w_o O(i,j) - w_l L(i,j) - w_f F(i,j)
```

where `G` is online observable unknown volume, `C` is feasible route cost,
`O` is predicted overlap with active teammate commitments, `L` is prospective
path-load imbalance and `F` is a bounded failed-attempt penalty.  No pair is
scored before R validates it.  Reallocation is triggered only by a logged
event: candidate covered/deleted, feasibility rejection, no progress for the
fixed timeout, vehicle unavailable, or an eligible cluster newly appearing.

Thus the paper's testable contribution is **not** “three UAVs fly at once.”
It is the measurable reduction of invalid commitments and redundant
exploration obtained by reachability-aware allocation and event-driven
reassignment.

## 5. Environment Contract and Geometry Audit

E1 remains an interface demonstration only.  E2 is the primary damaged
interior; E3 is a held-out topology used only after the E2 method and weights
are frozen.

E2 keeps the previously audited 46 m x 36 m x 4.2 m envelope, with occluded
branches, a loop, pockets, bottlenecks, collapse clusters, columns and
equipment obstacles.  Before every formal campaign, the generator must save:

- scene-generator commit and deterministic seed;
- mesh/PCD SHA-256 hashes;
- free-space connectivity report in the inflated collision map;
- clearance distribution for all doors and bottlenecks;
- count of reachable pockets, branches and loop connections;
- flight-band and wall-top audit; and
- a declaration that all scene metadata is excluded from runtime topics.

If the geometry audit finds an isolated or below-clearance region, it is not a
“harder benchmark.”  It is an invalid task region and must be excluded or
redesigned *before* a comparison campaign, never compensated by a route,
manual goal or hidden parameter change.

## 6. Prespecified Measurements

### 6.1 Mapping quality

All methods are compared against the same offline reference surface at fixed
voxel resolution and tolerance:

- surface precision, recall and F1;
- recall/F1 progress curves over wall-clock time;
- area under the recall-time curve over a fixed horizon H;
- T80, T90 and T95, reported as `not reached` when absent.

FUEL's own finish message is logged as a planner event, never substituted for
T80/T90/T95.  A map can be geometrically accurate where observed (high
precision) yet incomplete (low recall).

### 6.2 Mission and coordination

The formal table also reports: successful-run rate, makespan, total and
maximum per-UAV path length, collision count, minimum vehicle-to-obstacle and
vehicle-to-vehicle separation, planner-stall rate, candidate rejection rate,
reallocation rate, and communication bytes/messages.

The repeated-observation ratio is included **only after** per-UAV sensor/map
attribution is logged.  Its fixed definition will be:

```text
repeat_ratio = 1 - unique_team_observed_voxels / sum(per_uav_observed_voxels)
```

It must not be estimated from a single merged map, because that would make the
metric unidentifiable.

### 6.3 Replications and stopping

G0/G1 are diagnostic single runs.  After all gates pass, an initial
five-seed feasibility campaign is run for every method with the same frozen
seed set, preserving every run including failures.  It reports individual
points, mean and standard deviation; it is a feasibility table, not a claim of
population-level statistical significance.  The number of formal repetitions
is then determined from the observed variance and compute budget before E3 is
opened.  E3 is never used for parameter selection.

## 7. Mandatory Gates Before Any New Five-Run Table

1. Clean launch: only `/rosout` before a trial; one simulator/planner session.
2. Runtime-information audit: no truth, route, room labels or user goal reaches
   planner/coordinator topics.
3. Geometry audit: every intended passage is feasible after inflation; wall-top
   bypass is impossible within the flight band.
4. R audit: a deliberately infeasible candidate is logged as rejected or
   invalidated; the next candidate is selected without an unbounded planner
   loop.
5. Evidence audit: one stable RViz configuration displays observed occupancy,
   UAV pose, executed trajectory, planned trajectory and selected frontier.
   Upper-band points are clipped in this read-only display, preventing the
   false “purple ceiling” while keeping the planner map unchanged.
6. Persistence audit: the run directory contains request, exact parameters,
   diagnostics, event log, trajectory, snapshots, final PCD and evaluator
   output.

## 8. Execution Now

The next action is **G0 only**, using unmodified stock FUEL on frozen E2.
It is not another five-run experiment.  Its only question is whether the
current stack reaches FUEL completion, explicitly reports no coverable
frontier, or triggers the recorder's planner-stall condition.  The result
selects the next engineering action:

- `fuel_reported_finish`: run G1's deliberately infeasible-candidate audit;
- `planner_stall` with a saved trace: implement/test R before repeating;
- timeout or missing files: repair the launch/recording chain, not the
  exploration algorithm.

The exact, reproducible G0 commands are maintained in
`g0_stock_fuel_stall_audit_runbook.md`.
