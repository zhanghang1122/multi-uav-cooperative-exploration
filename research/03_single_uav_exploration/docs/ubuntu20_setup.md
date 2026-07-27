# Ubuntu 20.04 / ROS Noetic Setup

## 1. Gate Before This Stage

Run and retain the Stage 02 `base`, `medium`, and `complex` runtime reports
first. Stage 03 changes motion from a declared route to autonomous exploration;
it must not hide an unresolved sensing or mapping failure.

## 2. Install and Validate Official FUEL

Keep FUEL in an independent workspace because it is GPL-3.0:

```bash
mkdir -p ~/fuel_ws/src
cd ~/fuel_ws/src
git clone https://github.com/HKUST-Aerial-Robotics/FUEL.git

sudo apt-get update
sudo apt-get install -y libarmadillo-dev

cd ~
git clone -b v2.7.1 https://github.com/stevengj/nlopt.git
mkdir -p ~/nlopt/build
cd ~/nlopt/build
cmake ..
make -j2
sudo make install
sudo ldconfig

cd ~/fuel_ws
source /opt/ros/noetic/setup.bash
catkin_make -DCMAKE_BUILD_TYPE=Release -j2
```

Run the official office example before changing the map:

```bash
source ~/fuel_ws/devel/setup.bash
roslaunch exploration_manager rviz.launch
```

```bash
source ~/fuel_ws/devel/setup.bash
roslaunch exploration_manager exploration.launch
```

Click RViz `2D Nav Goal` once. Do not continue if the official example fails.

## 3. Build the Paper Workspace

The paper repository should already be under `~/catkin_ws/src`:

```bash
cd ~/catkin_ws
source /opt/ros/noetic/setup.bash
catkin_make -j2
source devel/setup.bash
```

Verify that ROS finds all three research packages:

```bash
rospack find ruins_urban_01
rospack find ruins_mapping_baseline
rospack find ruins_single_uav_exploration
```

## 4. Generate a Non-Destructive Overlay

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash

rosrun ruins_single_uav_exploration prepare_fuel_overlay.py \
  --fuel-workspace ~/fuel_ws \
  --variant base \
  --output-dir /tmp/ruins_fuel_overlay/base
```

Inspect `/tmp/ruins_fuel_overlay/base/manifest.json`. It must show
`upstream_checkout_modified: false`.

## 5. Run the Baseline

Terminal 1:

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch /tmp/ruins_fuel_overlay/base/fuel_exploration_base.launch
```

Terminal 2:

```bash
source ~/fuel_ws/devel/setup.bash
roslaunch exploration_manager rviz.launch
```

Terminal 3:

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_single_uav_exploration runtime_validation.launch \
  duration_s:=900 \
  result_file:=/tmp/ruins_fuel_base_runtime.json
```

Terminal 4:

```bash
source ~/fuel_ws/devel/setup.bash
source ~/catkin_ws/devel/setup.bash
roslaunch ruins_single_uav_exploration automatic_trigger.launch
```

The trigger waits for odometry and then publishes the same goal message type
used by RViz. It does not prescribe an exploration route.

## 6. Repeat in Controlled Order

After `base` passes, regenerate with `--variant medium`, then `complex`. Use a
new output directory and result filename for every run. Do not reuse stale
generated launch files after changing the repository or FUEL checkout.

## 7. Virtual Machine Notes

- allocate at least four CPU cores and 8 GB RAM if the host permits;
- keep FUEL `max_vel` and `max_acc` at the official 2.0 baseline initially;
- close Gazebo when running the FUEL point-cloud simulator;
- record wall-clock time because simulated time may slow under CPU load;
- a timeout caused by low real-time performance remains a failed trial and
  must be reported, not removed from the dataset.

## 8. Current Integration Boundary

This baseline uses FUEL's simulator and internal occupancy map. It does not
launch PX4, Prometheus, Gazebo, MARSIM, or Stage 02 OctoMap. Those stacks must
not be mixed into the first FUEL validation run.
