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

| Scene | Experimental role | Fixed scene design |
| --- | --- | --- |
| E1 Structured Interior | interface and single-UAV functional baseline | Compact structured interior. It confirms the sensing, mapping and evaluation interfaces; it is not a main-result scene. |
| E2 Damaged Building | fixed primary B1/B2/B3/P comparison scene | One common entry hall followed by three concurrently reachable, initially unknown wings: north office, south utility and east service loop. |
| E3 Industrial Wing | topology-generalization scene, never used for tuning P | Comparable footprint but different topology: rack-occluded workshop, asymmetric storage cells and a constrained east service spine. |

The generator writes two kinds of complexity evidence. Automatic geometry
counts (`wall`, `column`, `equipment`, `damage`, `overhead`) describe the actual
collision model. An **offline topology audit contract** defines named static
probes and validates them with the inflated flight-slice grid. It is only a
reproducibility artifact: it is not exported to Gazebo, MARSIM, FUEL or any
online exploration/controller node.

## Verified E2/E3 Design Parameters

The following values are from a clean generation using the current platform
profile (`D_eff=0.398 m`, inflation radius `0.199 m`, flight-slice grid
resolution `0.20 m`). Re-run the generator and cite its validation JSON if the
platform profile or geometry changes.

| Parameter | E2 Damaged Building | E3 Industrial Wing |
| --- | ---: | ---: |
| Workspace (m) | 42 x 32 x 4.2 | 44 x 34 x 4.2 |
| Reachable free-space fraction after inflation | 1.000 | 1.000 |
| Physical / inflated occupied footprint fraction | 0.104 / 0.220 | 0.099 / 0.199 |
| Entry-reachable major branches | 3 | 3 |
| Offline audit graph nodes / edges | 12 / 14 | 12 / 13 |
| Audit graph junctions / cycle rank / terminals | 4 / 3 / 4 | 4 / 2 / 5 |
| Wall segments | 63 | 46 |
| Columns / equipment / damage / overhead | 7 / 9 / 6 / 4 | 8 / 16 / 8 / 6 |
| Verified access/cross-link width (m) | 1.8--2.0 | 1.6--2.0 |
| Verified access/cross-link width (`D_eff`) | 4.52--5.03 | 4.02--5.03 |

`cycle rank` is `E - V + 1` for the connected offline audit graph. It provides
a reproducible statement that E2 has more alternative static connections than
E3; it does not give a route to the UAV. The listed passage widths are sampled
at named doorway/cross-link throats, not at the intentionally wider entry hall
or open room interiors.

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
