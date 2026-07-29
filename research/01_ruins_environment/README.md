# Ruins-Interior-01

Ruins-Interior-01 is a reproducible, thesis-oriented continuous 3D damaged-building environment for multi-UAV exploration on Ubuntu 20.04 / ROS Noetic / PX4 / Prometheus workflows.

This folder is a ROS package named `ruins_urban_01` inside the parent paper repository. Clone the parent repository under `~/catkin_ws/src`, then build or source the workspace so `$(find ruins_urban_01)` works in launch files.

The source representation is the Blender Python script in `scripts/generate_ruins_urban_01_blender.py`. The generated runtime assets are:

- `maps/pcd/*.pcd`: primary maps for MARSIM, FUEL, RACER, and point-cloud based planners.
- `meshes/obj/*.obj` and `meshes/dae/*.dae`: platform-neutral mesh exports.
- `gazebo/models/*` and `gazebo/worlds/*.world`: Gazebo Classic usable model/world files.
- `config/*.yaml`: scene dimensions, seeds, bounds, and integration hints.
- `launch/*.launch`: example ROS launch snippets/templates.

## Scene Design

- Size: 42 m x 32 m x 8 m.
- UAV collision diameter parameter: `D = 0.65 m`.
- Normal corridor width: 2.75 m.
- Narrow corridor width: 1.55 m.
- Squeeze passage width: 1.50 m (challenge variant only).
- Main vertical structure: an open high-bay hall, not a second storey.
- Features: irregular corridors, occluded forks, loops, dead ends, damaged room shells, bounded collapse clusters, structural columns, low-overhead passages, and a connected high-bay volume.

The paper main `challenge` scene contains 22 reference topology nodes,
28 traversable connections,
12 branch nodes,
7 independent loops,
5 dead ends, and
multiple obstacle-height bands and a visually open high-bay ceiling volume.
These reference paths exist only for generation-time validation and are not exposed as task partitions to the UAVs.

The scene is not pre-partitioned for UAV assignment. Any naming of rooms, forks, or sections exists only for modeling and debugging. Exploration algorithms should discover frontiers online from local sensing.

## Variants

| Variant | Seed | PCD points | Purpose |
|---|---:|---:|---|
| base | 240701 | 102319 | Basic validation and single-UAV bring-up |
| medium | 240702 | 145626 | Three-UAV debugging with denser rubble |
| complex | 240703 | 197902 | Complexity pilot only; not final paper data |
| challenge | 240704 | 250527 | Frozen paper main scene |

## Recommended Use

Update the parent Git repository inside the Ubuntu VM, then rebuild the catkin workspace:

```bash
cd ~/catkin_ws/src/multi-uav-cooperative-exploration
git fetch origin
git switch verified-runtime
git pull --ff-only
cd ~/catkin_ws
catkin_make -j2
source /opt/ros/noetic/setup.bash
source devel/setup.bash
```

For FUEL/RACER, copy or symlink a selected PCD into the package's `map_generator/resource` directory, then replace the original `map_pub` PCD argument and set the exploration bounding box:

```bash
roslaunch exploration_manager rviz.launch
roslaunch exploration_manager swarm_exploration.launch
```

Use these bounds:

```text
box_min_x = -21.0
box_max_x =  21.0
box_min_y = -16.0
box_max_y =  16.0
box_min_z =   0.0
box_max_z =   8.0
```

For Gazebo Classic/PX4, add `gazebo/models` to `GAZEBO_MODEL_PATH`, then open one of the world files:

```bash
source ~/catkin_ws/devel/setup.bash
source "$(rospack find ruins_urban_01)/setup_env.sh"
roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:=challenge
```

## Randomized Procedural Instances

Keep `base`, `medium`, `complex`, and `challenge` unchanged as fair, reproducible benchmark maps. Generate additional
random instances for generalization and stress tests:

```bash
cd "$(rospack find ruins_urban_01)"
python3 scripts/generate_random_ruins.py --profile challenge
```

The command prints the generated seed, world, PCD, and launch command. Omitting `--seed` creates a new
instance every time. To reproduce an exact instance or control clutter:

```bash
python3 scripts/generate_random_ruins.py   --profile challenge   --seed 20260724   --clutter-scale 1.20
```

Individual counts can also be controlled with `--rubble`, `--columns`, and `--collapsed-walls`.
Do not use `--fog` in the main geometry comparison; reserve it for a separate perception stress test.
Every generated instance writes a manifest under `validation/generated/` so failed runs remain reproducible.

For Prometheus, use the Gazebo world as the environment and keep UAV spawning near the entrance:

```text
UAV1: x=-19.0, y=-0.8, z=1.2
UAV2: x=-19.0, y= 0.0, z=1.6
UAV3: x=-19.0, y= 0.8, z=2.0
```

## Validation

Generation ran a basic centerline clearance check on the intended navigation graph. This does not prove a planner will succeed, but it catches accidental sealed corridors.

| Variant | Passed | Minimum clearance |
|---|---:|---:|
| base | True | 0.412 m |
| medium | True | 0.412 m |
| complex | True | 0.412 m |
| challenge | True | 0.364 m |

## Notes

- Start development on `base`, move to `medium`, use `complex` only for a complexity pilot, and reserve `challenge` for paper experiments.
- Use randomized starts, randomized obstacle seeds, and repeated trials later to prove autonomy rather than rehearsed trajectories.
- The included topology-related names are debug names only; do not use them as ground-truth task partitions in the algorithm.
- See `docs/design_basis.md` for the literature-informed design rationale and the limits of the benchmark.
- The default worlds are clear so geometry and planning difficulty can be evaluated independently. Use
  `variant:=complex_fog` only for a separate perception-degradation stress test.
