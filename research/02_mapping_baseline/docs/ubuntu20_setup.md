# Ubuntu 20.04 Setup

## 1. Install Runtime Packages

Deactivate Conda before compiling ROS packages:

```bash
conda deactivate
sudo apt update
sudo apt install -y \
  git \
  libglfw3-dev \
  libglew-dev \
  ros-noetic-octomap \
  ros-noetic-octomap-msgs \
  ros-noetic-octomap-ros \
  ros-noetic-octomap-server
```

## 2. Build Official MARSIM

Use a separate workspace so that MARSIM does not disturb the existing
PX4/Prometheus workspace:

```bash
mkdir -p ~/marsim_ws/src
cd ~/marsim_ws/src
git clone --branch ubuntu20 --single-branch \
  https://github.com/hku-mars/MARSIM.git

cd ~/marsim_ws
source /opt/ros/noetic/setup.bash
catkin_make -j2
```

The `-j2` limit is intentional for the virtual machine.

## 3. Place the Paper Repository

The full paper repository must replace the earlier standalone ZIP package.
Keeping both creates duplicate ROS package names.

First inspect the catkin source tree:

```bash
find ~/catkin_ws/src -name package.xml \
  -exec grep -H '<name>ruins_urban_01</name>' {} \;
```

If the old standalone directory still exists, move it outside `src`:

```bash
mv ~/catkin_ws/src/ruins_urban_01 \
  ~/ruins_urban_01_standalone_backup
```

Then clone the paper repository:

```bash
cd ~/catkin_ws/src
git clone \
  https://github.com/zhanghang1122/multi-uav-cooperative-exploration.git
```

If it is already cloned, update it:

```bash
cd ~/catkin_ws/src/multi-uav-cooperative-exploration
git pull
```

Build this workspace on top of MARSIM:

```bash
source /opt/ros/noetic/setup.bash
source ~/marsim_ws/devel/setup.bash
cd ~/catkin_ws
catkin_make -j2
source devel/setup.bash
```

## 4. Confirm Package Discovery

```bash
rospack find test_interface
rospack find octomap_server
rospack find ruins_urban_01
rospack find ruins_mapping_baseline
```

All four commands must return paths.

## 5. Run the Baseline

Terminal 1:

```bash
source /opt/ros/noetic/setup.bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_mapping_baseline mapping_baseline.launch variant:=base
```

Terminal 2:

```bash
source /opt/ros/noetic/setup.bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_mapping_baseline runtime_validation.launch duration_s:=90
```

## 6. Inspect the Reports

```bash
python3 -m json.tool /tmp/ruins_mapping_runtime.json
```

The runtime report must contain `"passed": true`. Stage 02 does not move the
UAV and does not claim complete map coverage.

## Common Failures

### `Resource not found: test_interface`

MARSIM was not sourced. Run:

```bash
source ~/marsim_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
```

### Local-cloud frame rejected

Check:

```bash
rostopic echo -n 1 /quad0_pcl_render_node/sensor_cloud/header
```

The expected frame for MARSIM's mapping input is `sensor`. The Ubuntu 20.04 CPU
renderer may publish the equivalent legacy name `/sensor`; the local-cloud gate
validates it and removes the leading slash before forwarding it to tf2 and
OctoMap. Do not switch OctoMap to the world-coordinate visualization cloud,
because its frame no longer identifies the correct LiDAR ray origin.

### OctoMap stays empty

Check the chain in order:

```bash
rostopic hz /quad0_pcl_render_node/sensor_cloud
rostopic hz /mapping/input_cloud
rostopic hz /octomap_binary
```

Then inspect TF:

```bash
rosrun tf tf_echo world sensor
```

If the cloud frame is not `sensor`, inspect MARSIM's `sensor_cloud` publisher
and TF instead of feeding either the world-coordinate visualization cloud or
the global truth cloud to OctoMap.

### RViz is slow

Keep `use_gpu:=false`, close Gazebo, start with `variant:=base`, and reduce the
RViz point size. MARSIM does not require Gazebo for this stage.
