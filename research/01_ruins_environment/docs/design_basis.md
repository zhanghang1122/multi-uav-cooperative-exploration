# Ruins-Urban-01 v2: Literature-Informed Design Basis

This scene is a compact, reproducible UAV benchmark inspired by recurring challenges reported in
subterranean and multi-UAV exploration research. It is not a geometric copy of a DARPA course and
does not claim that obstacle count alone measures environmental complexity.

## Evidence Used

1. DARPA Subterranean Challenge program overview:
   https://www.darpa.mil/research/programs/darpa-subterranean-challenge
   The official challenge description highlights constrained passages, sharp turns, large drops and
   climbs, inclines, steps, falling debris, and complex underground networks.
2. CERBERUS field report:
   https://arxiv.org/abs/2201.07067
   Reports multi-level urban underground structures, narrow or inaccessible spaces, degraded sensing,
   denied communications, and robot-specific local/global planning.
3. Autonomous teamed subterranean exploration:
   https://arxiv.org/abs/2111.06482
   Emphasizes large-scale multi-branched topology, steep slopes, diverse geometry, communication loss,
   map sharing, and global frontier coordination.
4. Team MARBLE multi-agent autonomy:
   https://arxiv.org/abs/2110.04390
   Identifies diverse topology and terrain, degraded sensing, limited communication, and metric-topological
   planning as core field challenges.
5. FUEL:
   https://github.com/HKUST-Aerial-Robotics/FUEL
   Provides the PCD-map workflow and a strong single-UAV exploration baseline on Ubuntu 20.04/ROS Noetic.
6. RACER:
   https://arxiv.org/abs/2209.08533
   Provides a decentralized multi-UAV baseline using asynchronous limited communication.
7. MARSIM:
   https://arxiv.org/abs/2211.10716
   Motivates the point-cloud-first export for light-weight LiDAR and multi-UAV simulation.

## Implemented Complexity Dimensions

| Dimension | Complex variant |
|---|---:|
| Physical size | 42 x 32 x 8 m |
| Reference topology nodes | 40 |
| Traversable graph edges | 45 |
| Branch nodes | 14 |
| Independent loops | 6 |
| Dead ends | 6 |
| Vertical connectors | 3 |
| Reference graph length | 240.11 m |
| Minimum validated centerline clearance | 0.394 m |
| UAV collision diameter D | 0.65 m |
| Narrow/squeeze widths | 1.45 m / 1.22 m |

Geometric complexity comes from connected structure, not random clutter alone. The scene combines an
irregular main spine, two ground-level loops, east-side branches, six dead ends, a partial upper network,
three vertical connectors, low ceilings, hanging beams, altitude-change gates, repetitive columns, and
occluded junctions. Rubble is generated with fixed seeds and constrained so it cannot accidentally seal
the geometric clearance-test corridors. These corridors validate environment connectivity only and are
never provided to an exploration planner.

## Intended Experimental Use

- `base`: integration and single-UAV bring-up.
- `medium`: multi-UAV debugging with two vertical connectors and five loops.
- `complex`: main thesis experiments and ablation studies.

Run at least 20 repeated trials per method with varied start yaw, sensor noise, communication loss, and
additional obstacle seeds. Report coverage-time curves, success rate, total fleet path length, repeated
coverage, minimum inter-UAV distance, map completeness, and runtime. A single successful video is not
evidence of autonomy.

The navigation graph stored in validation files is a generator oracle used only to ensure that the world
is physically traversable. Exploration code must not read it.
