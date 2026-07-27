# Mapping Baseline Experiment Protocol

## Objective

Demonstrate that a bounded local LiDAR stream, rather than prior access to the
complete ruins map, drives incremental 3D occupancy mapping.

## Independent Variables

- scene variant: `base`, `medium`, `complex`;
- renderer: CPU for the controlled baseline;
- map resolution: 0.18 m;
- LiDAR horizon: 15 m.

## Controlled Variables

- initial pose: `[-19.2, 0.0, 1.35, 0.0]`;
- MARSIM `ubuntu20` branch;
- Mid-360 sensing pattern;
- world frame;
- OctoMap sensor model;
- repository commit.

## Recorded Outputs

- local-cloud and occupancy-map screenshots at declared times;
- `/tmp/ruins_mapping_runtime.json`;
- ROS log directory;
- scene variant and repository commit;
- virtual-machine CPU and memory allocation;
- real-time factor or measured wall-clock duration.

## Required Trial Order

1. static sensor/interface check on `base`;
2. static sensor/interface check on `medium`;
3. static sensor/interface check on `complex`;
4. one repeated `complex` check to confirm deterministic wiring.

The complete truth cloud must remain hidden in the paper RViz view. A separate
truth visualization may be captured only for a clearly labelled offline
comparison figure.

## Evidence Naming

Create one directory per run:

```text
experiments/results/YYYYMMDD_HHMM_variant_commit/
```

Use these filenames:

```text
runtime.json
t000_local_and_map.png
t030_local_and_map.png
t060_local_and_map.png
t090_local_and_map.png
notes.md
```

## Pass/Fail Rule

A trial passes when all runtime interface checks pass. A timeout, missing local
cloud, missing OctoMap output, or truth-topic wiring is a failed trial and must
not be silently discarded. This stage makes no map-completeness claim.
