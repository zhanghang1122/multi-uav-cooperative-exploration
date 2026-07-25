# Demo 03: FUEL Autonomous Exploration and 3D Occupancy Mapping

## What This Demo Is

This is the official FUEL single-UAV exploration baseline:

```text
unknown office-like PCD environment
  -> simulated sensing
  -> online occupancy map
  -> frontier information structure
  -> hierarchical exploration planning
  -> minimum-time trajectory
```

The recorded run showed the vehicle exploring previously unknown space while
the 3D occupancy map grew in RViz. This is described as 3D occupancy mapping,
not as a verified `octomap_server` output.

## What This Demo Is Not

- It is not the unfinished FUEL-to-Prometheus/PX4 bridge.
- It is not multi-UAV task allocation.
- It does not use the Ruins-Urban-01 map unless the FUEL map configuration is
  explicitly changed.

## Install the Official Baseline

FUEL documents Ubuntu 20.04 and ROS Noetic support. Keep it in a separate
workspace:

```bash
mkdir -p ~/fuel_ws/src
cd ~/fuel_ws/src
git clone https://github.com/HKUST-Aerial-Robotics/FUEL.git

sudo apt-get install -y libarmadillo-dev

cd ~
git clone -b v2.7.1 https://github.com/stevengj/nlopt.git
cd ~/nlopt
mkdir build
cd build
cmake ..
make -j2
sudo make install
sudo ldconfig

cd ~/fuel_ws
source /opt/ros/noetic/setup.bash
catkin_make -DCMAKE_BUILD_TYPE=Release -j2
```

## Run

Terminal 1:

```bash
bash demos/demo03_fuel_exploration/scripts/run_rviz.sh
```

Terminal 2:

```bash
bash demos/demo03_fuel_exploration/scripts/run_exploration.sh
```

Use RViz `2D Nav Goal` once to trigger exploration, as required by the
upstream demo.

## Use Ruins-Urban-01

After the official office baseline passes, use one of this repository's maps,
for example:

```text
research/01_ruins_environment/maps/pcd/Ruins-Urban-01_complex.pcd
```

The example map-publisher launch files under `launch/` show the intended map
paths. Do not change the planner and the environment in the same experiment:
first validate the upstream baseline, then change only the map path and bounds.
