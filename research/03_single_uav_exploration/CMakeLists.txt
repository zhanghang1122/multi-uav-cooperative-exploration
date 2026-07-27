cmake_minimum_required(VERSION 3.0.2)
project(ruins_single_uav_exploration)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/evaluate_surface_coverage.py
  scripts/exploration_runtime_monitor.py
  scripts/finalize_paper_trial.py
  scripts/prepare_fuel_overlay.py
  scripts/trigger_exploration.py
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
