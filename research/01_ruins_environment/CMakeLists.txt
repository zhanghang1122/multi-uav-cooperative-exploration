cmake_minimum_required(VERSION 3.0.2)
project(ruins_urban_01)

find_package(catkin REQUIRED)

catkin_package()

install(DIRECTORY
  blender
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
