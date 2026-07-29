# Ruins-Interior-01: Literature-Informed Design Basis

This scene is a compact, reproducible UAV benchmark inspired by recurring challenges reported in
subterranean and multi-UAV exploration research. It is not a geometric copy of a DARPA course and
does not claim that obstacle count alone measures environmental complexity.

## Evidence Used

1. DARPA Subterranean Challenge program overview:
   https://www.darpa.mil/research/programs/darpa-subterranean-challenge
   The official description identifies autonomous mapping and navigation in human-made urban underground
   structures, tunnels, and caves under degraded perception and difficult terrain as the target problem.
2. Zhou B, Pan J, Gao F, Shen S. FUEL: Fast UAV Exploration Using Incremental Frontier Structure and
   Hierarchical Planning. IEEE Robotics and Automation Letters, 2021.
   https://doi.org/10.1109/LRA.2021.3051563
   Supports frontier-driven autonomous exploration as the single-UAV baseline and uses bounded 3D map space.
3. Ribeiro M, Basiri M. Efficient 3D Exploration with Distributed Multi-UAV Teams: Integrating Frontier-Based
   and Next-Best-View Planning. Drones, 2024, 8(11):630.
   https://doi.org/10.3390/drones8110630
   Supports evaluating distributed multi-UAV 3D exploration with completion time, explored volume, and overlap.
4. Peng X. An autonomous Unmanned Aerial Vehicle exploration platform with a hierarchical control method for
   post-disaster infrastructures. IET Cyber-Systems and Robotics, 2024.
   https://doi.org/10.1049/csy2.12107
   Supports defining a known 3D task boundary while leaving infrastructure geometry unknown, and evaluating
   reconstructed-map accuracy and completeness separately.
5. Campos-Macias L, Aldana-Lopez R, de la Guardia R, Parra-Vilchis J, Gomez-Gutierrez D. Autonomous
   navigation of MAVs in unknown cluttered environments. Journal of Field Robotics, 2021, 38:307-326.
   https://doi.org/10.1002/rob.21959
   Supports a layered architecture: online mapping, field-of-view-safe planning, and local dynamic trajectory generation.
6. Wen C, Dong W, Xie W, Cai M, Liu R. Distributed cooperative area search method for UAV swarms based on
   revisit mechanism. Acta Aeronautica et Astronautica Sinica, 2023, 44(11):327561.
   https://doi.org/10.7527/S1000-6893.2022.27561
   Supports online information updates and repeated-run statistical comparison rather than one scripted trajectory.
7. GA-HP: A game-assisted hierarchical planner for multi-UAV coverage in unknown environments.
   Aerospace Science and Technology, 2025, 166:110624.
   https://doi.org/10.1016/j.ast.2025.110624
   Supports separating centralized task allocation from safe local planning in unknown environments.

## Implemented Complexity Dimensions

| Dimension | Challenge variant |
|---|---:|
| Physical size | 42 x 32 x 8 m |
| Reference topology nodes | 25 |
| Traversable graph edges | 33 |
| Branch nodes | 13 |
| Independent loops | 9 |
| Dead ends | 5 |
| Altitude-changing free-space links | 3 |
| Reference graph length | 209.9 m |
| Minimum validated centerline clearance | 0.45 m |
| UAV collision diameter D | 0.65 m |
| Narrow/squeeze widths | 1.55 m / 1.30 m |

Geometric complexity comes from connected structure, not random clutter alone. The challenge scene combines
multi-branch ground loops, 5 dead ends, an open high-bay volume,
3 altitude-changing free-space links, damaged room shells,
three bounded collapse zones, controlled partitions, low-overhead structures, structural columns, and occluded
junctions. It contains no separate second floor and no hidden spatial island. All interior obstacles are generated
with fixed seeds and constrained so they cannot accidentally seal the validated reference routes.

## Intended Experimental Use

- `base`: integration and single-UAV bring-up.
- `medium`: multi-UAV debugging only; it is not the paper main environment.
- `complex`: complexity pilot; do not report it as the final paper main environment.
- `challenge`: frozen main environment for B1/B2/B3/proposed-method comparisons.

Run at least 20 repeated trials per method with varied start yaw, sensor noise, communication loss, and
additional obstacle seeds. Report coverage-time curves, success rate, total fleet path length, repeated
coverage, minimum inter-UAV distance, map completeness, and runtime. A single successful video is not
evidence of autonomy.

The navigation graph stored in validation files is a generator oracle used only to ensure that the world
is physically traversable. Exploration code must not read it. In particular, high-bay nodes are not floor labels,
route priors, or targets; they only confirm that high free space is connected to the entry.
