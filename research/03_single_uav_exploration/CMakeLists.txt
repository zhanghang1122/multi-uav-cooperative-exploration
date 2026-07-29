cmake_minimum_required(VERSION 3.0.2)
project(ruins_single_uav_exploration)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/fuel_depth_to_cloud.py
  scripts/evaluate_independent_map.py
  scripts/prepare_fuel_overlay.py
  scripts/record_single_uav_trial.py
  scripts/trigger_exploration.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch rviz
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
