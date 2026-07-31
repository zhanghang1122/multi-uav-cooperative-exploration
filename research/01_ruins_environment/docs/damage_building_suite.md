# Damaged Building Benchmark Suite

This document specifies the V2 candidate environment family for cooperative UAV
exploration. It replaces neither the online planner nor the paper method. It
defines fixed, reproducible geometry for controlled experiments. E2-V2 and
E3-V2 have passed generator-level geometry QA only; they do not enter the paper
experiment protocol until their Gazebo/MARSIM sensor interface is verified.

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
| E2-V2 Damaged Branch Loop | fixed primary B1/B2/B3/P comparison scene | Screened common entry followed by three similarly costly, initially unknown wings: north damage/gallery, south damage/gallery and an east service loop. |
| E3-V2 Industrial Spine | topology-generalization scene, never used for tuning P | Comparable-scale but asymmetric topology: rack-occluded workshop, serial damaged storage cells and an S-shaped east service spine. |

The generator writes two kinds of complexity evidence. Automatic geometry
counts (`wall`, `column`, `equipment`, `damage`, `overhead`) describe the actual
collision model. An **offline topology audit contract** defines named static
probes and validates them with the inflated flight-slice grid. It is only a
reproducibility artifact: it is not exported to Gazebo, MARSIM, FUEL or any
online exploration/controller node.

## Verified V2 Generator Parameters

The following values are from a clean generation using the current platform
profile (`D_eff=0.398 m`, inflation radius `0.199 m`, flight-slice grid
resolution `0.20 m`). Re-run the generator and cite its validation JSON if the
platform profile or geometry changes.

| Parameter | E2-V2 Damaged Branch Loop | E3-V2 Industrial Spine |
| --- | ---: | ---: |
| Workspace (m) | 46 x 36 x 4.2 | 48 x 38 x 4.2 |
| Reachable free-space fraction after inflation | 1.000 | 1.000 |
| Physical / inflated occupied footprint fraction | 0.093 / 0.196 | 0.091 / 0.178 |
| Entry-reachable major branches | 3 | 3 |
| Entry-to-major-branch distance (m) | 55.2--59.0; spread 6.9% | 45.6--60.2; asymmetric spread 32.0% |
| Offline audit graph nodes / edges | 16 / 16 | 13 / 14 |
| Audit graph junctions / cycle rank / terminals | 4 / 1 / 5 | 4 / 2 / 5 |
| Collision boxes | 96 | 91 |
| Wall segments | 60 | 47 |
| Columns / equipment / damage / overhead | 10 / 11 / 8 / 6 | 11 / 15 / 10 / 7 |
| Verified access/cross-link width (m) | 1.2--2.0 | 1.0--2.0 |
| Verified access/cross-link width (`D_eff`) | 3.02--5.03 | 2.51--5.03 |

`cycle rank` is `E - V + 1` for the connected offline audit graph. It measures
the declared, grid-validated alternative connection count; it is neither a
runtime map nor a route. E2-V2 is deliberately **balanced** to make a three-UAV
allocation comparison fair. E3-V2 is deliberately **asymmetric** and is held
out for topology generalization after P has been frozen. The listed passage
widths are sampled at named doorway/cross-link throats, not at the intentionally
wider entry hall or open room interiors.

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
  --output-dir /tmp/damage_building_suite_v2
```

The default profile is the versioned
`config/platform_profiles/fuel_marsim_os128_v1.json` in this package. A
temporary platform-profile file may be supplied only when recalibrating the
same verified platform; it is not required for normal experiment replay.

Inspect `/tmp/damage_building_suite_v2/previews/*.svg` and each validation JSON
before launching a world. Generation itself does not modify a runtime planner.

For a first visual check in Gazebo Classic, use the E2 world after successful
generation:

```bash
gazebo /tmp/damage_building_suite_v2/worlds/Coop-Building-E2V2-Damaged-Branch-Loop.world
```

The same world can later be supplied to the simulator after its sensing and
mapping interface is verified. Do not connect it to FUEL or a multi-UAV method
until the scene assets and offline validation report have been reviewed.
