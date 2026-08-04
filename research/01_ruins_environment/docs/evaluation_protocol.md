# Evaluation Protocol for Cooperative Unknown-Environment Exploration

This protocol fixes the evaluation contract for the B1/B2/B3/P study.  It is
deliberately defined before the multi-UAV methods are implemented so that no
metric, threshold, route prior or truth-map information is changed after a
result is observed.

## Experimental Rules

- E1 is an interface and single-UAV baseline scene.  E2 is the fixed primary
  comparison scene.  E3 is used only after the proposed method is frozen, as a
  topology-generalization test.
- Every method receives the same sensor model, dynamics limits, workspace
  boundary and initial pose pattern.  No method receives a route, room graph,
  frontier list, goal location or ground-truth map at runtime.
- The ground-truth PCD is used only by offline evaluators after a trial ends.
- Each method-scene pair is repeated at least five times.  If an algorithm uses
  stochastic sampling, the same recorded seeds are used across compared
  methods.  Results are reported as mean +/- standard deviation, with every
  failed/timeout trial retained.
- A coverage threshold is declared as `not_reached`, not replaced with the
  timeout value, when a trial does not cross it.

## A. Map Quality and Exploration Progress

The primary reference is the interior-facing surface PCD.  It excludes exterior
envelope faces and obstacle bottoms that cannot be observed from the aircraft's
reachable indoor flight space.

| ID | Metric | Definition | Direction | Used by |
| --- | --- | --- | --- | --- |
| M1 | Surface Precision | matched reconstructed surface voxels / reconstructed surface voxels | higher | B1/B2/B3/P |
| M2 | Surface Recall | matched reference surface voxels / reference surface voxels | higher | B1/B2/B3/P |
| M3 | F1 | harmonic mean of M1 and M2 | higher | B1/B2/B3/P |
| M4 | `C_s(t)` | offline surface Recall at elapsed time `t` | higher | B1/B2/B3/P |
| M5 | `T80`, `T90`, `T95` | first time at which `C_s(t)` reaches 0.80, 0.90 or 0.95 | lower | B1/B2/B3/P |

`C_s(t)` is calculated from stored online-map snapshots.  `Tq` is linearly
interpolated between the two adjacent snapshots that straddle the threshold.
It measures exploration efficiency, whereas M1--M3 measure final map quality.

## B. Mission Efficiency

| ID | Metric | Definition | Direction | Used by |
| --- | --- | --- | --- | --- |
| E1 | Mission makespan | elapsed time from the common start trigger until all active UAVs finish | lower | B1/B2/B3/P |
| E2 | Total path length | `L_sum = sum_i L_i` | lower | B1/B2/B3/P |
| E3 | Team speedup | `S_N = T_B1 / T_N` at the same coverage threshold | higher | B2/B3/P |
| E4 | Parallel efficiency | `eta_N = T_B1 / (N * T_N)` | higher | B2/B3/P |
| E5 | Success rate | completed trials without timeout or collision / all trials | higher | B1/B2/B3/P |

`T_B1` and `T_N` must use the same scene and the same threshold, normally
`T90`.  If B1 does not reach `T90`, the comparison is reported at the highest
predeclared threshold reached by every compared method; this exception is
stated in the table caption.

## C. Cooperative Allocation and Redundancy

These are the metrics that distinguish a real cooperative system from three
independent vehicles.

| ID | Metric | Definition | Direction | Used by |
| --- | --- | --- | --- | --- |
| C1 | Cross-UAV repeated mapping rate | `(sum_i |V_i| - |union_i V_i|) / |union_i V_i| * 100%`, where `V_i` is the reference-matched surface-voxel set observed by UAV `i` | lower at equal M2/M3 | B2/B3/P |
| C2 | Unique mapping contribution | `U_i = |V_i - union_(j != i) V_j|` | descriptive | B2/B3/P |
| C3 | Contribution imbalance | coefficient of variation `std(U_i) / mean(U_i)` | lower | B2/B3/P |
| C4 | Path-load imbalance | coefficient of variation `std(L_i) / mean(L_i)` | lower | B2/B3/P |
| C5 | Assignment conflict rate | duplicated simultaneous frontier/task claims / all assignment events | lower | B2/B3/P |
| C6 | Reallocation response | number and latency of valid reassignments after a task becomes invalid or a UAV fails | lower latency | P robustness only |

C1 is the paper's *repetition rate*.  It is not a simple count of a vehicle
passing through the same corridor twice: revisits can be necessary for loop
closure, obstacle avoidance and returning through a corridor.  C1 measures
cross-UAV duplication of reconstructed, reference-matched surfaces.  Some
overlap is useful for map fusion, therefore the goal is not zero overlap; the
fair claim is a lower C1 while retaining equal or better map quality.

## D. Safety, Computation and Communication

| ID | Metric | Definition | Direction | Used by |
| --- | --- | --- | --- | --- |
| S1 | Collision count | physical obstacle or inter-UAV collision events | lower; target 0 | B1/B2/B3/P |
| S2 | Minimum clearance | minimum trajectory-to-obstacle and pairwise UAV separation | higher, subject to common planning envelope | B1/B2/B3/P |
| S3 | Planning-cycle latency | mean and 95th percentile decision-to-trajectory latency | lower | B1/B2/B3/P |
| S4 | Coordination latency | mean and 95th percentile allocation/reallocation latency | lower | B2/B3/P |
| S5 | Communication volume | total serialized map, task and trajectory bytes exchanged | lower | B3/P |
| S6 | Communication robustness | success, M2/M3 and E1 degradation under declared delay/loss conditions | smaller degradation | P robustness only |

Real energy consumption is not a primary metric until a validated battery and
motor-power model is available.  Path length is retained as an energy proxy;
it must not be labelled as measured energy consumption.

## Paper Outputs

The paper will not use raw RViz screenshots as quantitative evidence.  It will
produce the following reproducible figures and tables:

1. Scene-parameter table: size, rooms, loops, dead ends, bottlenecks,
   obstruction/damage elements, planner envelope and connectivity validation.
2. Map-quality and efficiency table: M1--M5 and E1--E5, mean +/- standard
   deviation over five trials.
3. `C_s(t)` curve with 95% confidence/error band; snapshots at matched times
   illustrate autonomous map growth.
4. Multi-UAV coordination table: C1--C5, S1--S5 for B2/B3/P.
5. Trajectory/map figure using identical viewpoints for every compared method.
6. E3 generalization and optional communication/failure robustness table only
   after P is frozen.

## Literature Basis

- The single-UAV baseline follows FUEL's incremental Frontier structure and
  hierarchical exploration-planning formulation: [Zhou et al., IEEE Robotics
  and Automation Letters, 2021](https://doi.org/10.1109/LRA.2021.3051563).
- Safe and reachable Frontier candidates are treated as a prerequisite rather
  than a visualization feature, following [Senarathne and Wang, Robotics and
  Autonomous Systems, 2015](https://doi.org/10.1016/j.robot.2015.05.009).
- The cooperative measurements separate map sharing, communication and team
  allocation effects, consistent with [Mahdoui et al., Journal of Intelligent
  & Robotic Systems, 2020](https://doi.org/10.1007/s10846-019-01062-6) and
  [Bayer and Faigl, Autonomous Robots, 2026](https://doi.org/10.1007/s10514-025-10234-3).
- Coverage-progress and multi-UAV efficiency measures are retained as formal
  outcomes rather than screenshots, consistent with [Huang et al., Aerospace
  Science and Technology, 2025](https://doi.org/10.1016/j.ast.2025.110624).
