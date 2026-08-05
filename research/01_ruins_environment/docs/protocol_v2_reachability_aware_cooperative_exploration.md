# Frozen Protocol V2: Reachability-Aware Three-UAV Cooperative Exploration

> **Superseded for new simulation work by**
> `protocol_v2_1_review_and_execution.md`.  V2 is retained as an audit trail
> for the prior decision; V2.1 corrects the fairness boundary between the
> single-UAV navigation substrate and the later coordination comparison.

## 0. Status and Decision

This document supersedes `protocol_v1_indoor_cooperative_exploration.md` for
all work after 2026-08-05. It freezes the research question, comparison
methods, runtime-information boundary, acceptance gates and paper-facing
measurements before further simulator modification.

The prior E1 five-run table and all E2 runs are **pipeline pilots**, not
manuscript results. They establish that online occupancy, trajectories and
offline reference-map evaluation can be recorded. They do not establish an
algorithmic advantage because the current FUEL baseline can stall after it
selects a locally infeasible candidate.

## 1. Research Question

> In a fixed but runtime-unknown damaged-building interior, can three UAVs
> sharing only online map and team state improve mapping completeness and
> mission efficiency over single-UAV and uncoordinated multi-UAV exploration,
> while rejecting or reassigning Frontier candidates that are not safely
> reachable?

The contribution is deliberately narrow. This study does **not** claim a new
SLAM method, semantic recognition, target rescue, radio-silent coordination,
or an end-to-end learned flight controller. Simulator odometry is an assumed
localization input; any GPS-denied SLAM claim requires a later, independent
localization experiment.

## 2. What "Autonomous" Means Here

At runtime, every vehicle receives only its sensor observations, current pose,
vehicle state, motion limits and messages permitted by the communication
setting. It receives no ground-truth PCD, room identity, preassigned area,
target coordinate, flight route, waypoint list or manually imposed visit
order.

The system must repeatedly:

1. update an online 3D occupancy/ESDF map;
2. extract and cluster unknown/free-space boundary candidates;
3. discard candidates that are unsafe or unreachable in the current inflated
   free space;
4. allocate only feasible candidates;
5. invalidate and reallocate a commitment when a candidate disappears,
   becomes unreachable, is covered by a teammate, or records no progress.

The offline reference PCD is used only after the run to calculate quality
metrics. It never enters a planner, allocator, stop decision or visualization
that affects a run.

## 3. Literature-Anchored Design Rules

| Anchor | Verified journal finding adopted here | Protocol consequence |
| --- | --- | --- |
| Zhou et al., FUEL, RA-L 2021 | Incremental Frontier structure plus global coverage, local view refinement and minimum-time trajectory generation is an established single-UAV baseline. | Retain unmodified FUEL as B1; do not call it a cooperative method. |
| Senarathne & Wang, RAS 2015 | A frontier detector should report only safe and reachable boundary contours; reachability is a first-class exploration condition. | A candidate is eligible for allocation only after reachability/safety validation. |
| Bayer & Faigl, Autonomous Robots 2026 | Multi-robot studies separate navigation from coordination and compare time, travelled distance and coverage over repeated trials; shared map/waypoint/position information enables strong allocation baselines but has communication cost. | Separate vehicle navigation from assignment; use repeated trials, report makespan, distance, coverage curve, redundancy and communication. |
| Peng, IET Cyber-Systems & Robotics 2024 | Post-disaster UAV exploration requires online map completeness, collision avoidance and next-best-view selection; it uses several constrained infrastructure scenes rather than one decorative obstacle field. | E2 is a parameter-audited damaged interior, with E3 held out for generalization only. |
| Amigoni et al., Autonomous Robots 2026 | Map completeness and a stopping decision must be evaluated separately from a planner's internal "no frontier" event. | FUEL finish is logged, but formal completion is assessed from a fixed offline recall threshold/time curve. |

Full citations and links are in `literature_anchor_v2.md`.

## 4. Fixed Methods and Comparison Order

The following methods are the entire first paper study. No reinforcement
learning, topology/semantic module, rescue task or communication-by-gesture is
added before this table is complete.

| ID | Method | Runtime information | Purpose |
| --- | --- | --- | --- |
| B1 | One UAV, stock FUEL | Its own online map and pose | Single-UAV Frontier baseline. |
| B2 | Three independent B1 vehicles | Each vehicle's own online map and pose | Shows the effect of adding vehicles without coordination and exposes repeated exploration. |
| B3 | Three UAVs, shared map plus feasible-nearest assignment | Shared map updates, feasible Frontier-cluster positions and vehicle states | Conventional cooperative baseline. The assignment minimizes team route cost using a Hungarian/auction equivalent. |
| P | Three UAVs, shared map plus reachability-aware utility assignment and event-driven reallocation | Same as B3 plus online-only gain, committed-target state, progress/failure state and inter-vehicle exclusion state | Proposed method. |

### Proposed Method P

At each allocation epoch, construct a set of **feasible Frontier clusters**.
For UAV `i` and cluster `j`, a candidate is admitted only when the current
inflated map has a collision-free path and the local motion planner accepts a
dynamically feasible prefix. Ineligible candidates are not scored.

For admitted pairs, use the auditable online utility

```text
U(i,j) = w_g G(j) - w_c C(i,j) - w_o O(i,j) - w_l L(i,j) - w_f F(i,j)
```

where `G` is predicted observable unknown volume, `C` is feasible route cost,
`O` is predicted overlap with teammate commitments/covered volume, `L` is
post-assignment path-load imbalance, and `F` is a bounded penalty from prior
failed attempts at the same candidate. Every term is derived only from the
current online state and is logged per decision.

Assignments are one-to-one for the active planning horizon. A commitment is
revoked and the allocation recomputed when: (a) a new eligible cluster is
created, (b) the assigned cluster is covered or deleted, (c) the motion
planner rejects it, (d) execution reports no progress for the predeclared
timeout, or (e) a UAV becomes unavailable. This is the proposed method's
testable difference from a static nearest-frontier rule.

## 5. Environment Contract

### Primary environment: E2

E2 is a fixed damaged-building interior, not a random collection of boxes:

- footprint: 46 m x 36 m; sensor/map volume: 4.2 m high;
- operational flight band: 0.80--2.05 m; nominal entry height: 1.50 m;
- three initially occluded branches, one loop, five pockets, four bottlenecks,
  six collapse clusters, twelve columns and ten equipment obstacles;
- physical walls extend above the operational flight envelope, preventing an
  invalid wall-top shortcut;
- every nominal doorway/corridor is audited against the vehicle collision
  envelope and planner inflation before a formal run.

The scene generator produces a geometry audit containing component counts,
minimum clearance, connectivity and the reference PCD hash. A failed audit
invalidates the scene rather than being repaired by a hidden route or a manual
goal.

### Generalization environment: E3

E3 is frozen and unseen during P weight selection. It is used only after the
E2 comparison table is complete to test whether B3/P conclusions persist under
a distinct interior topology. E1 remains an interface demonstration only.

## 6. Evaluation Plan

### Runtime evidence

Each run saves the exact scene hash, parameter files, random seed, trajectories,
map snapshots, Frontier-cluster events, assignments, rejection reasons,
reallocation events, collision/minimum-clearance events and communication
bytes/messages.

### Offline map evidence

Against the same reference surface for every method, calculate voxel-surface
Precision, Recall and F1 at fixed resolution/tolerance. Plot recall and F1
over time. Report T80/T90/T95 as the earliest time reaching the stated recall;
report `not reached` rather than substituting planner finish time.

### Team evidence

Report mission success rate, makespan, total path length, maximum individual
path length, aggregate and per-UAV unique observed surface, repeated-observation
ratio, path-load imbalance, collision count, minimum inter-UAV separation,
candidate-rejection rate, reallocation rate, planner-stall rate and
communication volume.

### Statistics

First execute a feasibility campaign: five deterministic pilot repetitions for
each method with fixed seeds. A formal comparison is allowed only after all
methods pass the gates below; it then uses the same predeclared seed set,
reports mean, standard deviation, every failed run and paired per-seed
differences. No parameter is tuned on E3.

## 7. Non-Negotiable Acceptance Gates

No five-run formal table is started until the following are true in one clean
E2 run:

1. observed map, UAV pose, executed trajectory and current target are all
   visible from one recorded RViz configuration;
2. there is no hidden route, goal, area label or reference map consumed at
   runtime;
3. every selected target carries a logged feasibility result;
4. a deliberately infeasible candidate produces a logged rejection or
   reallocation, not an unbounded `PLAN_TRAJ` loop;
5. completion emits a recorder summary, final PCD, trajectory, event log and
   snapshots in a persistent experiment directory;
6. all output files are readable by the evaluator and reproduce the recorded
   metrics.

Until Gate 4 passes, a FUEL stop/stall is a diagnostic observation, not an
experiment failure to hide nor a result to compare.

## 8. Execution Sequence

1. **G0 -- freeze and audit B1:** reproduce the current stock-FUEL stall with
   a clean launcher and capture its candidate/planner failure trace. No map or
   scene parameter tuning in this step.
2. **G1 -- implement feasible-candidate supervisor:** add only the online
   feasibility/rejection/retry event interface required by B1-R. Demonstrate
   one recorded recovery; otherwise stop and diagnose.
3. **G2 -- stabilize E2 single-UAV baseline:** run B1 and B1-R on E2 only
   after G1 passes. Select B1-R as the navigation substrate only if it improves
   completion without using forbidden prior information.
4. **G3 -- B2:** deploy three identical, independent stabilized agents with a
   synchronized mission start and collision monitor.
5. **G4 -- B3:** add shared map state and feasible-nearest one-to-one
   allocation; keep the same navigation substrate as B2.
6. **G5 -- P:** add the fixed utility, commitment invalidation and reallocation
   logs. Compare B2/B3/P under identical seeds.
7. **G6 -- E3:** one held-out generalization campaign after P is frozen.

Changing the research question, scene geometry, sensor model, motion limits,
map-evaluation definition or utility after G2 requires a new protocol version;
it does not silently overwrite results.
