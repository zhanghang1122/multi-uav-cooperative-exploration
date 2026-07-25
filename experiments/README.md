# Experiments

This directory defines the paper-oriented experiment interface. It intentionally does not contain fabricated results.

## Result Schema

Each run should create one row in `results.csv` with at least:

```text
run_id, git_commit, method, config, world_profile, world_seed, repetition,
uav_count, success, collision_count, completion_time_s, final_coverage,
fleet_path_m, max_uav_path_m, repeated_exploration_ratio,
assignment_conflicts, reallocations, mean_decision_time_ms, max_decision_time_ms
```

Store detailed time series under:

```text
results/<experiment_id>/<run_id>/
  manifest.yaml
  coverage.csv
  uav_1_trajectory.csv
  uav_2_trajectory.csv
  uav_3_trajectory.csv
  assignments.csv
  runtime.csv
```

Large rosbag files should remain outside Git and be archived with the paper's data release when required.

## Minimum Paper Matrix

1. Fixed-world comparison: all methods x base/medium/complex x five repetitions.
2. Core ablations: complex x five repetitions.
3. Unseen-world generalization: frozen methods x ten test seeds x three repetitions.
4. Failure recovery: blocked frontier, invalid target, or one-UAV withdrawal.

Never add measured values to this repository until the corresponding run manifests and raw CSV files exist.
