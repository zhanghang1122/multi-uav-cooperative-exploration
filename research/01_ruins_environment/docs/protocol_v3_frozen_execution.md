# Protocol V3: Frozen Execution Plan

## Status and precedence

This is the only active execution protocol for the paper project.  Earlier
`protocol_v1*` and `protocol_v2*` files are historical design records.  They
must not be used to justify a new experiment, parameter change, or code change.

The research question, comparison groups, runtime information contract, and
evaluation protocol below are frozen.  Choosing a software implementation that
passes the reproducibility gate does not change the scientific method.

## Paper scope

**Working title:** Reachability-constrained and event-triggered multi-UAV
cooperative exploration for 3-D mapping of unknown damaged building interiors.

The paper studies three UAVs that start from a common entry in a fixed but
runtime-unknown building.  They autonomously explore and construct an online
3-D occupancy map.  This is not a SLAM, target-recognition, formation-flight,
or semantic-navigation paper.

### Runtime information contract

Allowed inputs:

- each UAV's state estimate and onboard depth/LiDAR measurements;
- its online occupancy map and messages permitted by the compared method;
- a common bounded mission volume and physical flight-safety limits.

Forbidden inputs:

- truth PCD, room identifiers, branch labels, topology annotations;
- manually specified targets, routes, waypoints, or exploration order;
- preassigned spatial zones.

Truth geometry is used only after a completed or failed run for offline map
evaluation.

## Frozen proposed method P

P consists of three coupled but separately testable mechanisms:

1. **Reachability-constrained frontier state management.** A frontier cluster
   is marked `eligible`, `deferred`, or `invalid` using only the current
   inflated online map, configured flight band, and collision-free connectivity
   test.  An ineligible candidate cannot be assigned.
2. **Marginal-utility one-to-one assignment.** For UAV `i` and eligible
   frontier cluster `j`, assignment is based on online information gain,
   feasible route cost, expected overlap with other assignments, and predicted
   workload imbalance.  It is not nearest-frontier selection or area
   prepartitioning.
3. **Event-triggered reassignment.** Allocation is recomputed only when a
   frontier is covered, invalidated, becomes infeasible, materially changes
   value, or when a UAV completes/fails/stalls.  Timer-only reassignment is not
   the proposed method.

The paper claims the closed-loop combination above, not that any individual
ingredient is globally new.

## Frozen comparison groups

| ID | Method | Purpose |
| --- | --- | --- |
| G0 | One UAV, stock frontier explorer | Establish the unmodified reference and expose base failures. |
| B1 | One UAV, reachability-constrained frontier state management | Isolate the value of reachability handling. |
| B2 | Three B1 UAVs without shared allocation | Show that simply adding aircraft can create redundant work. |
| B3 | Three UAVs with shared map and feasible distance-based assignment, no event reassignment | Isolate ordinary cooperation. |
| P | Three UAVs with all three proposed mechanisms | Evaluate the complete method. |

All groups use identical vehicle constraints, sensing, flight band, map
resolution, geometry, map evaluator, and run seeds.

## Scene policy

### E1: pilot only

E1 remains the completed single-UAV integration and evaluation-pipeline check.
It is allowed in a presentation as preliminary evidence but is not a main paper
comparison scene.

### E2: fixed primary benchmark

E2 is the sole main comparison scene.  Its accepted geometry must satisfy all
of the following before G0 is run:

- Gazebo collision geometry, rendered/sensed geometry, and truth PCD derive
  from the same source model.
- Walls close the active flight band: either a physical ceiling exists or every
  boundary wall exceeds the maximum permitted flight height.  Flying over an
  interior wall is prohibited.
- The evaluated free-space domain is one physically connected component after
  obstacle inflation.
- Each intended throat is auditable against the vehicle diameter plus the
  configured inflation and safety margin.
- The vertical non-bypass margin above the active flight envelope, after the
  planner radius is included, is at least 0.20 m (two map cells at the frozen
  0.10 m evaluation/mapping scale).
- Declared first-order branch route burdens are recorded as scene covariates.
  A damaged building may be intentionally asymmetric; method fairness is
  obtained by running every group on the identical sealed scene and reporting
  workload imbalance, not by imposing an unsupported branch-length threshold.
- The entry hides multiple initially unknown branches.  The scene has at least
  one loop, multiple terminal/occluded pockets, a damaged obstruction, and
  genuine alternative routes.
- No fog, random layout changes, dynamic obstacles, scene labels, or predefined
  exploration targets are present in the primary comparison.

The current E2 assets are not paper evidence until this audit passes.  A failed
audit causes rejection of the asset, not another ad-hoc obstacle edit.

### E3: held-out generalization scene

E3 is generated once, sealed before P is tuned, and used only for G0-versus-P
generalization validation after E2 comparisons are complete.

## Reproducibility gate

Before any formal E2 experiment, one candidate exploration stack must pass a
five-run integration check in a simple audit scene:

- no route, waypoint, target, or truth-map input;
- online map, executed trajectory, frontier lifecycle, and stop reason are
  recorded;
- at least four of five runs finish normally or terminate with a classified
  algorithmic failure rather than a process/interface failure;
- no manual flight action, RViz dependency, or hidden source patch is required.

If stock FUEL fails this gate, it remains G0 only.  The research method is not
altered; the implementation base is selected by this predeclared criterion.

## Run protocol and failure classification

Each formal condition uses five fixed seeds and an isolated output directory.
Each directory must include configuration hashes, process versions, run seed,
trajectory, online-map snapshots, frontier/allocation events, stop reason, and
offline evaluation JSON.

Classify every unsuccessful run as exactly one of:

1. `integration_failure`: missing topic, TF/frame mismatch, crashed process,
   invalid generated asset, or recorder failure;
2. `algorithm_failure`: all interfaces healthy but the method has no valid
   eligible action or reaches the stall condition;
3. `safety_failure`: collision, flight-band breach, or separation violation.

Only category 2 or 3 counts toward the method's formal success rate.  Category
1 invalidates that run and must be repaired before repetition.

The stall condition is fixed as: eligible work remains, vehicle displacement is
below 0.05 m, and no new executable trajectory is published for 45 s.

## Evaluation protocol

The truth map is voxelized only offline at 0.10 m resolution with one-voxel
matching tolerance.  Main reported results are:

- mission success rate;
- surface precision, recall, and F1;
- recall-time curve and its area under curve;
- T80; T90/T95 are reported as `not reached` when applicable;
- makespan, total traveled distance, and per-UAV distance;
- repeated-observation rate and workload imbalance;
- collision count, minimum inter-UAV separation, planner stalls;
- invalid-frontier rejections and reassignment success/latency.

## Ordered execution gates

| Gate | Required evidence | Decision before next gate |
| --- | --- | --- |
| 0 | This protocol and fixed configuration inventory | Freeze accepted. |
| 1 | E2 geometry, clearance, connectivity, flight-band, and source-consistency audit | Accept or reject E2 as a whole. |
| 2 | Five-run stack reproducibility report | Select stable base; do not patch failed base ad hoc. |
| 3 | G0 five-run baseline on accepted E2 | Establish reference. |
| 4 | B1 component tests and five-run B1 result | Validate reachability mechanism. |
| 5 | B2 five-run result | Quantify uncoordinated multi-UAV behavior. |
| 6 | B3 five-run result | Quantify ordinary shared-map allocation. |
| 7 | P five-run result plus ablation logs | Test the complete proposal. |
| 8 | E3 G0/P held-out result | Test generalization without retuning. |

No later gate may be started while its predecessor lacks the listed evidence.

## Literature basis

- Zhou et al., FUEL, IEEE Robotics and Automation Letters, 2021:
  https://doi.org/10.1109/LRA.2021.3051563
- Zhang and Xing, Cooperative task assignment of multi-UAV system, Chinese
  Journal of Aeronautics, 2020:
  https://doi.org/10.1016/j.cja.2020.02.009
- Hu et al., Fault-tolerant cooperative navigation of networked UAV swarms for
  forest fire monitoring, Aerospace Science and Technology, 2022:
  https://doi.org/10.1016/j.ast.2022.107494
- Huang et al., A lightweight GA-HP algorithm for multi-UAVs coverage path
  planning in unknown environment, Aerospace Science and Technology, 2025:
  https://doi.org/10.1016/j.ast.2025.110624
- Xiang et al., Key technologies for autonomous cooperation of unmanned swarm
  systems in complex environments, Acta Aeronautica et Astronautica Sinica,
  2022: https://doi.org/10.7527/S1000-6893.2022.27570
