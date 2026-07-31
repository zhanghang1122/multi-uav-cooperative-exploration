# Damaged Building Benchmark Suite

This document specifies the candidate environment family for cooperative UAV
exploration. It replaces neither the online planner nor the paper method. It
defines fixed, reproducible geometry for controlled experiments.

## Runtime Boundary

At runtime an aircraft receives only the workspace boundary and its live sensor
stream. It is not given a room list, navigation graph, target, precomputed
route, frontier list, truth PCD or topology report. The exported PCD files are
strictly offline ground truth for map-quality evaluation.

## Platform Constraint

The current profile uses FUEL `exploration_manager/launch/algorithm.xml` with
`sdf_map/obstacles_inflation=0.199 m`; therefore the active effective planning
diameter is `D_eff=0.398 m`. The generator inflates every collision box by
`0.199 m` at a 1.5 m flight slice and rejects any scene whose free space is not
at least 98.5 percent connected to the physical entry. This is an offline QA
rule, not an online planning input.

## Scene Roles

| Scene | Experimental role | Structural complexity |
| --- | --- | --- |
| E1 Structured Interior | interface and single-UAV functional baseline | 8 rooms, 1 loop, 2 dead ends; generated geometry: 4 columns, 3 equipment obstacles, 1 damage cluster, 2 overhead elements |
| E2 Damaged Building | fixed primary B1/B2/B3/P comparison scene | 16 rooms, 4 loops, 6 dead ends, 4 bottlenecks, 6 damage clusters; generated geometry: 7 columns, 9 equipment obstacles, 4 overhead elements |
| E3 Industrial Wing | topology-generalization scene, never used for tuning P | 20 rooms, 6 loops, 10 dead ends, 6 bottlenecks, workshop racks and service wing; exact geometry counts are read from its validation report |

Room, junction, loop, dead-end, bottleneck and turn counts are controlled
topology-design parameters. The validation JSON separately reports automatic
geometry counts by role (`wall`, `column`, `equipment`, `damage`, `overhead`)
and is the only source used for obstacle-count claims. Visual density alone is
not treated as complexity.

## Three-Dimensional Structure

E2/E3 contain columns, damage, equipment and partial overhead elements. They
do not claim a hidden second floor. A full inaccessible upper story would make
exploration completion ambiguous unless a physically observable, reachable
opening and flight strategy were separately validated.

## Literature Relationship

The suite follows the controlled-scenario practice used in unknown-environment
UAV exploration and cooperative search studies: progressively validate the
perception-planning interface, compare methods in one fixed main scene, then
test generalization in a topologically distinct scene. The project literature
protocol records the applicable sources, including CJA 2021 unknown-map
obstacle avoidance and AST 2017/2022/2025 cooperative/GPS-denied studies.

## Regeneration

```bash
rosrun ruins_urban_01 generate_damage_building_suite.py \
  --output-dir /tmp/damage_building_suite_v1
```

The default profile is the versioned
`config/platform_profiles/fuel_marsim_os128_v1.json` in this package. A
temporary platform-profile file may be supplied only when recalibrating the
same verified platform; it is not required for normal experiment replay.

Inspect `/tmp/damage_building_suite_v1/previews/*.svg` and each validation JSON
before launching a world. Generation itself does not modify a runtime planner.

For a first visual check in Gazebo Classic, use the E2 world after successful
generation:

```bash
gazebo /tmp/damage_building_suite_v1/worlds/Coop-Building-E2-Damaged-Building.world
```

The same world can later be supplied to the simulator after its sensing and
mapping interface is verified. Do not connect it to FUEL or a multi-UAV method
until the scene assets and offline validation report have been reviewed.
