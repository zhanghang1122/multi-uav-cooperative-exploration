cmake_minimum_required(VERSION 3.0.2)
project(ruins_multi_uav_coordination)

find_package(catkin REQUIRED)

catkin_package()

install(DIRECTORY config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)

