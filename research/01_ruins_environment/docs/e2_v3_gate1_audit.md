# E2 Gate 1 Geometry Audit

## Scope

This report evaluates the output of
`generate_e2_primary_benchmark.py` against Protocol V3.  It is a source-level,
offline geometry audit.  It does not claim that FUEL, RViz, ROS topics, or a
multi-UAV stack has run successfully.

## Generated artifact

- Scene: `Coop-Building-E2-Primary-Damaged-Interior`
- Generation seed: `fixed-e2-v5`
- Footprint: `46.0 m x 36.0 m`
- Interior height: `4.2 m`
- Active flight volume: `z = 0.80 m` to `2.05 m`
- Planning radius: `0.199 m`
- Map/voxel scale: `0.10 m`

The generator exports the Gazebo world, collision/visual mesh, sensor-rendering
PCD, and offline-only interior-reference PCD from the same box list.  This part
of the source-consistency contract is satisfied.

## Positive checks

| Check | Measured evidence | Result |
| --- | --- | --- |
| Runtime truth leakage | No route, goal, room, branch, or truth-map input is exported to the online planner | Pass |
| Reachable free-space component | `reachable_free_fraction = 1.0` at the audited flight slice | Pass |
| Doorway clearance | Four declared bottlenecks are `1.2 m` physical, `0.802 m` after stated planning clearance | Pass |
| Intended passage probes | `1.4 m`, `1.4 m`, and `1.6 m` planning-free widths | Pass |
| Required topology | 3 initial branches, 1 loop, 5 terminal/occluded pockets, 6 collapse clusters, 17 vertical obstacle groups | Pass |
| PCD sampling density | Surface lattice diagonal `0.099 m`, no coarser than the `0.10 m` map cell | Pass |

## Recorded design covariate

### Primary branch burdens are not an acceptance test

The audited branch-anchor route lengths are:

| Branch | Route burden |
| --- | ---: |
| North | 38.8 m |
| South | 37.8 m |
| East | 53.0 m |

The east-to-south difference is `40.2%`.  This is retained as an intentional
damaged-building asymmetry.  No reviewed journal establishes a universal 25%
branch-balance requirement, so enforcing one would be arbitrary.  All compared
methods instead use this same sealed geometry, and the paper reports per-UAV
distance and workload imbalance to show how each method handles it.

## Corrected geometry result

The revised fixed blueprint uses a minimum architectural wall top of `2.55 m`.
With the frozen maximum flight height `2.05 m` and planning radius `0.199 m`,
the measured non-bypass margin is now `0.301 m`. This exceeds the Protocol V3
minimum of `0.20 m`.

## Gate decision

**Gate 1 status: PASS (source geometry only).**

The world, collision/visual mesh, simulator PCD, and offline reference PCD are
generated from one box list; the E2 geometry may proceed to the base-stack
reproducibility gate. This does **not** yet prove that the runtime planner
enforces `z = 0.80–2.05 m`: that is an explicit Stage 2 runtime gate. No formal
G0/B1/B2/B3/P paper result may be reported until both gates pass.
