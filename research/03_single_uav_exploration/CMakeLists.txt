cmake_minimum_required(VERSION 3.0.2)
project(ruins_single_uav_exploration)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/diagnose_baseline_trial.py
  scripts/evaluate_coverage_timeseries.py
  scripts/evaluate_surface_coverage.py
  scripts/exploration_runtime_monitor.py
  scripts/finalize_paper_trial.py
  scripts/paper_evidence_recorder.py
  scripts/prepare_fuel_overlay.py
  scripts/trigger_exploration.py
  scripts/validate_paper_run.py
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
