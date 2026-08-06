cmake_minimum_required(VERSION 3.0.2)
project(ruins_urban_01)

find_package(catkin REQUIRED)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/collect_platform_profile.py
  scripts/derive_geometry_constraints.py
  scripts/diagnose_e2_branch_coverage.py
  scripts/generate_damage_building_suite.py
  scripts/generate_e2_primary_benchmark.py
  scripts/g1_reachability_gate_audit.py
  scripts/prepare_fuel_baseline_overlay.py
  scripts/apply_fuel_geometric_recovery.py
  scripts/audit_fuel_overlay_contract.py
  scripts/record_fuel_b1_trial.py
  scripts/validate_flight_envelope.py
  scripts/evaluate_surface_map.py
  scripts/audit_surface_alignment.py
  scripts/build_e2_coverable_surface_reference.py
  scripts/filter_online_map_for_viz.py
  scripts/launch_e2_b1_trial.py
  scripts/publish_uav_pose_marker.py
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
