cmake_minimum_required(VERSION 3.0.2)
project(ruins_urban_01)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/collect_platform_profile.py
  scripts/derive_geometry_constraints.py
  scripts/generate_damage_building_suite.py
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
