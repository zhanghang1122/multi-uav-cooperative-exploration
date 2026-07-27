# Multi-UAV Cooperative Exploration

This is the research repository for a paper on cooperative autonomous
exploration and 3D mapping by multiple UAVs in complex unknown ruins.

The repository is organized around the paper workflow, not around one Gazebo
world. The implemented modules currently cover the Ruins-Urban-01 environment
and an implementation-ready MARSIM-to-OctoMap mapping baseline. Autonomous
exploration, multi-UAV coordination, and evaluation code will be added as
separate numbered modules only after each preceding stage passes its declared
test.

## Repository Structure

```text
.
|-- research/
|   |-- README.md
|   |-- 01_ruins_environment/    ROS environment package and generated assets
|   `-- 02_mapping_baseline/     MARSIM-to-OctoMap baseline; runtime pending
|-- demos/
|   |-- demo01_single_uav_obstacle_avoidance/ audited single-UAV baseline
|   |-- demo02_ego_swarm_10uav/  ten-agent EGO-Swarm baseline
|   `-- demo03_fuel_exploration/ official FUEL exploration baseline
|-- docs/
|   `-- demo_audit.md            accepted and rejected historical claims
|-- tools/
|   `-- verify_repository.py     repository-wide structural checks
|-- CITATION.cff
|-- LICENSE
`-- THIRD_PARTY.md
```

The three demos are historical baselines. They are not numbered stages of the
paper implementation and are not presented as a single integrated system.

## Current Research Module

### 01. Ruins-Urban-01 environment

[`research/01_ruins_environment/`](research/01_ruins_environment/README.md)
contains:

- deterministic `base`, `medium`, and `complex` benchmark scenes;
- seeded randomized ruins generation;
- Blender Python source generation;
- PCD, OBJ, DAE, Gazebo model, SDF, and world exports;
- ROS launch/config examples for Gazebo Classic, FUEL, RACER, and MARSIM;
- geometry, topology, and centerline-clearance validation.

This module is a ROS package named `ruins_urban_01`. The directory name is
different from the ROS package name by design.

## Ubuntu 20.04 Quick Start

Clone the paper repository into the catkin source tree:

```bash
cd ~/catkin_ws/src
git clone https://github.com/zhanghang1122/multi-uav-cooperative-exploration.git

cd ~/catkin_ws
catkin_make
source devel/setup.bash
source src/multi-uav-cooperative-exploration/research/01_ruins_environment/setup_env.sh

roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:=complex
```

Catkin searches recursively and finds the nested `ruins_urban_01` package.
Do not keep another package with the same `<name>ruins_urban_01</name>` under
`~/catkin_ws/src`, or `catkin_make` will report a duplicate package.

## Research Roadmap

The planned module order is:

1. `01_ruins_environment`: environment generation and validation;
2. `02_mapping_baseline`: MARSIM local sensing and online OctoMap baseline;
3. `03_single_uav_exploration`: repeatable single-UAV baseline;
4. `04_multi_uav_coordination`: three-UAV allocation, map sharing, and avoidance;
5. `05_experiments`: fixed-map comparison, unseen-seed generalization, and ablation.

The second module is implementation-ready but still requires its declared
Ubuntu runtime validation. Empty or unverified implementations are not
presented as completed experimental work.

## Historical Demo Policy

Each demo has an independent README, status file, evidence, and launch wrapper.
The repository makes only these claims:

| Demo | Accepted result | Boundary |
|---|---|---|
| Demo 1 | D435i color, depth, and point-cloud perception of a Gazebo obstacle | End-to-end EGO avoidance flight was not verified |
| Demo 2 | Ten `fake_drone` agents planned and moved after a manual trigger | Not ten PX4 vehicles and not unknown-space task allocation |
| Demo 3 | Official FUEL single-UAV exploration produced online map growth | Not the unfinished FUEL-to-PX4 bridge |

See [`docs/demo_audit.md`](docs/demo_audit.md) before reusing a demo.

## Validation

From the repository root:

```bash
python3 tools/verify_repository.py
```

This checks the paper-repository layout, all three demo records, ROS/XML
metadata, Python syntax, fixed environment assets, and navigation-clearance
reports. Ubuntu runtime tests remain necessary for ROS and Gazebo behavior.

## Reproducibility Rule

Fixed benchmark scenes are used for controlled comparisons. Seeded unseen
scenes are used for generalization tests. Every reported trial must record the
scene seed, git commit, method configuration, start poses, stopping criterion,
coverage curve, trajectory, collisions, task assignments, and runtime.

## License and Citation

Original repository code and assets use the MIT License. Upstream planners and
simulators retain their own licenses; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
Use [`CITATION.cff`](CITATION.cff) for software citation until the paper is
published.
