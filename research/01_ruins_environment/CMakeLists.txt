cmake_minimum_required(VERSION 3.0.2)
project(ruins_urban_01)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/collect_platform_profile.py
  scripts/derive_geometry_constraints.py
  scripts/generate_damage_building_suite.py
  scripts/generate_e2_primary_benchmark.py
  scripts/prepare_fuel_baseline_overlay.py
  scripts/record_fuel_b1_trial.py
  scripts/evaluate_surface_map.py
  scripts/summarize_b1_trials.py
  scripts/trigger_position_neutral_exploration.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY
  config
  docs
  experiments
  gazebo
  launch
  maps
  meshes
  scripts
  validation
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
