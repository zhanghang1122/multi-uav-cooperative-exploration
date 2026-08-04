# Frozen Protocol V1: Indoor Cooperative Exploration and Mapping

## Research Question and Scope

This study asks whether three UAVs can improve the **efficiency and completeness
of autonomous exploration and online three-dimensional mapping** in an unknown,
damaged building interior without receiving a route, room partition, target
coordinate, Frontier list, or ground-truth map at runtime.

The current platform provides simulator odometry. The present claim is therefore
**online occupancy mapping under assumed odometry**, not a completed claim of
GPS-denied SLAM robustness. Localization error (for example ATE/RPE) becomes a
separate required experiment before any GPS-denied localization claim is made.

## Fixed Environment and Vertical Contract

E2 is the primary comparison environment: 46 m x 36 m x 4.2 m, with three
initially occluded branches, one loop, five pockets, four declared bottlenecks,
six collapse clusters, twelve columns and ten equipment obstacles. E1 remains
an interface-validation scene only. E3 is held out until the proposed method is
frozen, and is not used for tuning.

The physical scene has **no ceiling**. The operational flight volume is
`0.80 <= z <= 2.05 m`; the nominal start is `z = 1.50 m`. This is a declared
indoor mission boundary. The generator verifies that the maximum planning
centre height plus FUEL's 0.199 m obstacle envelope remains below the lowest
architectural wall top (2.35 m). Consequently, a planner cannot transform a
doorway/loop decision into an illegal wall-top shortcut. The sensor and map
volume remain 4.2 m, and the RViz upper clipping is presentation-only.

## Methods and Comparison Order

| ID | Method | Status and purpose |
| --- | --- | --- |
| B1 | Official FUEL, one UAV | Frozen single-UAV Frontier baseline. |
| B1-R | B1 plus a failure-triggered, local reachable-candidate retry | Engineering diagnostic only until a run records a real recovery event. |
| B2 | Three independent B1 agents | Isolates the effect of adding vehicles without task coordination. |
| B3 | Three UAVs, shared map, conventional reachable-Frontier allocation | Cooperative baseline. |
| P | Three UAVs, shared map, reachability-aware Frontier-cluster assignment with invalidation and reallocation | Proposed method. |

The proposed method is not allowed to use preassigned rooms, routes, hidden
topology, or true map coverage. Its allocation state may contain only
information made online from shared occupied/free/unknown map state, vehicle
state, reachable candidate cost, and the declared communication model.

The implementation sequence is strict: first validate the altitude contract
with `launch_e2_b1_trial.py`, which refuses a node-name collision with a stale
FUEL session before it starts the experiment;
then archive stable B1 trials; then validate a triggered B1-R recovery event;
then implement B2, B3 and P in that order. No E3 tuning occurs before P is
frozen.

## Evaluation Contract

All methods receive the same sensor model, motion limits, start pattern,
operational flight volume, map resolution, timeout and offline reference PCD.
The reference PCD is never provided to the runtime planner.

Primary map measures are surface Precision, Recall and F1. Exploration progress
is the offline surface-recall curve `C_s(t)`, with `T80`, `T90` and `T95` marked
not reached when absent. Team comparison reports makespan, total path length,
success rate, collision count, minimum separation, planning latency,
cross-UAV repeated mapping rate, unique contribution, path-load imbalance,
assignment-conflict rate and communication volume. Five repetitions are pilot
evidence; the formal comparison uses paired random seeds and reports every
failure, with the repeat count fixed before the B2/B3/P table is generated.

## Literature Basis

The protocol adopts a reachable-Frontier baseline because safe reachable
Frontier detection is itself a documented exploration problem, rather than a
display artifact. It separates mapping quality from exploration efficiency and
team redundancy because cooperative mapping papers distinguish map sharing,
communication constraints and allocation effects.

1. Zhou, B. et al. *FUEL: Fast UAV Exploration Using Incremental Frontier
   Structure and Hierarchical Planning*. IEEE Robotics and Automation Letters,
   2021. https://doi.org/10.1109/LRA.2021.3051563
2. Senarathne, P. J., and Wang, D. *Incremental Algorithms for Safe and
   Reachable Frontier Detection*. Robotics and Autonomous Systems, 2015.
   https://doi.org/10.1016/j.robot.2015.05.009
3. Mahdoui, A., Fremond, G., and Natalizio, E. *Communicating Multi-UAV System
   for Cooperative SLAM-Based Exploration*. Journal of Intelligent & Robotic
   Systems, 2020. https://doi.org/10.1007/s10846-019-01062-6
4. Huang, X. et al. *A Lightweight GA-HP Algorithm for Multi-UAVs Coverage Path
   Planning in Unknown Environment*. Aerospace Science and Technology, 2025.
   https://doi.org/10.1016/j.ast.2025.110624
5. Bayer, J., and Faigl, J. *Decentralized Multi-Robot Exploration Under
   Low-Bandwidth Communications*. Autonomous Robots, 2026.
   https://doi.org/10.1007/s10514-025-10234-3
