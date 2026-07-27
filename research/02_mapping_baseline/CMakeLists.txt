cmake_minimum_required(VERSION 3.0.2)
project(ruins_mapping_baseline)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/inspect_pcd.py
  scripts/local_cloud_gate.py
  scripts/reference_trajectory.py
  scripts/runtime_monitor.py
  scripts/uav_visualizer.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY
  config
  docs
  experiments
  launch
  rviz
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
