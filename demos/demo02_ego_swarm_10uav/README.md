# Demo 02: Ten-Agent EGO-Swarm

## What This Demo Is

This is the upstream EGO-Planner-Swarm simulation configured to wait for an
explicit trigger before ten agents start moving toward their predefined
targets.

The default upstream setup uses `fake_drone` to convert position commands to
odometry. This makes ten-agent visualization practical in a virtual machine,
but it is not equivalent to ten PX4 SITL vehicles.

## Historical Result

The recorded run showed ten simulated agents moving through the generated
obstacle field after `/traj_start_trigger` was published. The retained image is
under `evidence/`.

## Prepare

Install the upstream repository in a separate workspace:

```bash
sudo apt-get install -y libarmadillo-dev
mkdir -p ~/uav_ego_planner_demo
cd ~/uav_ego_planner_demo
git clone https://github.com/ZJU-FAST-Lab/ego-planner-swarm.git
```

Apply the narrowly scoped ROS Noetic build dependency fix:

```bash
python3 demos/demo02_ego_swarm_10uav/scripts/patch_noetic_build.py \
  ~/uav_ego_planner_demo/ego-planner-swarm
```

Build:

```bash
cd ~/uav_ego_planner_demo/ego-planner-swarm
source /opt/ros/noetic/setup.bash
catkin_make -DCMAKE_BUILD_TYPE=Release -j1
```

Generate the manual-trigger launch wrappers:

```bash
python3 demos/demo02_ego_swarm_10uav/scripts/create_manual_launches.py \
  ~/uav_ego_planner_demo/ego-planner-swarm \
  ~/uav_ego_planner_demo/manual_launch
```

Both scripts stop without changing files when the expected upstream structure
does not match.

## Run

Terminal 1:

```bash
bash demos/demo02_ego_swarm_10uav/scripts/run.sh
```

Terminal 2, after RViz shows ten stationary agents:

```bash
bash demos/demo02_ego_swarm_10uav/scripts/trigger.sh
```

## Research Limitation

The default target coordinates are predefined. This demonstrates decentralized
multi-agent trajectory planning and collision avoidance, not autonomous
frontier allocation or unknown-environment exploration.

