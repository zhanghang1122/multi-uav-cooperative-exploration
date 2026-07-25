# Historical Demo Audit

## Audit Rule

A demo is accepted only when its final recorded state has positive evidence.
A launch command, a generated trajectory, or a planner log alone is not
treated as proof of successful flight. Unfinished fixes are not published as
working code.

## Decisions

| Item | Recorded evidence | Decision |
|---|---|---|
| P230 + D435i perception | Point cloud published at about 14 Hz; Gazebo box appeared in color, depth, and point-cloud views | Keep as a perception baseline |
| P230 + D435i + OctoMap + EGO flight | Planner repeatedly reported `the drone is in obstacle`; `world -> uav1/d435i_link` had an incorrect height; no later success was confirmed | Exclude the TF bridge and autonomous-flight claim |
| APF local-point-cloud demo | Planner produced velocities, but the vehicle later crossed the visual point obstacles, stopped early, and dropped out of command control | Exclude as a successful avoidance demo |
| Ten-agent EGO-Swarm | Ten simulated agents were shown moving after `/traj_start_trigger`; a video and summary were retained | Keep with an explicit `fake_drone` limitation |
| FUEL office exploration | Official FUEL exploration was run and a map-growth result/video was retained | Keep as the official single-UAV baseline |
| FUEL-to-Prometheus/PX4 bridge | Perception and yaw/control integration remained under repair | Exclude |
| RACER multi-UAV exploration | Build stopped at generated-message dependency errors; no completed run was recorded | Exclude |
| Rescue/recognition pipeline | Multiple integration problems remained and it is outside the current paper scope | Exclude |

## Consequences for Repository Claims

1. Demo 1 verifies sensing, not end-to-end autonomous avoidance.
2. Demo 2 verifies a lightweight multi-agent planning simulation, not ten PX4
   aircraft.
3. Demo 3 is a single-UAV exploration baseline, not the proposed three-UAV
   ruins system.
4. Ruins-Urban-01 is the current validated artifact. Later navigation and
   cooperative exploration results must be added only after repeatable trials
   and recorded metrics exist.

