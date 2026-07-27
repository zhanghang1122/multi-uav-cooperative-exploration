# Stage 03 Experiment Protocol

## Objective

Verify that an official FUEL single-UAV planner can autonomously finish the
Ruins-Urban-01 environment using only online local sensing.

## Controlled Variables

- FUEL checkout commit;
- paper repository commit;
- PCD SHA-256;
- initial pose `[-19.2, 0.0, 1.35]`;
- map size `[42.0, 32.0, 10.0]`;
- exploration box inset by 0.35 m;
- FUEL official algorithm parameters;
- virtual-machine CPU/RAM;
- trigger mechanism and timeout.

## Trial Sequence

1. official FUEL office map, one successful run;
2. `base`, three repeated runs;
3. `medium`, three repeated runs;
4. `complex`, three repeated runs;
5. at least five unseen seeded ruins after the fixed maps pass.

The first implementation checkpoint requires one pass on each fixed variant.
The repeated and unseen-seed trials belong to the paper dataset.

## Evidence Per Trial

Store:

```text
experiments/results/YYYYMMDD_HHMM_variant_commit/
  manifest.json
  runtime.json
  final_occupancy.pcd
  surface_coverage_tol1.json
  surface_coverage_tol2.json
  summary.csv
  figure_reconstruction_topdown.svg
  notes.md
```

`runtime.json` must be produced by `exploration_runtime_monitor.py`, not written
by hand. `final_occupancy.pcd` must be captured from
`/sdf_map/occupancy_all`. The complete simulator PCD may be read only by the
offline evaluator after the exploration process has ended.

Run `finalize_paper_trial.py` after every completed trial. It copies the
temporary runtime files into a unique result directory, computes both strict
and relaxed surface metrics, records hashes and software provenance, and
generates the same three-panel vector figure for every run. Manual RViz
screenshots may be retained as supplementary evidence, but they are not the
primary quantitative result.

Metric bounds and figure bounds are recorded separately. A diagnostic run may
display its complete search height while retaining a predeclared lower-layer
metric volume. Never change metric bounds after inspecting a method's result.

The paper dataset consists of all repeated trials, including failures. Failed
trials without a captured map retain their ROS log and a failure note outside
the finalizer. Never replace or delete a failed run. A single successful run
is suitable for pipeline validation but not for a comparative paper claim.

## Pass Rule

A trial passes only if:

1. odometry is received;
2. the trigger reaches FUEL's waypoint bridge;
3. at least one B-spline trajectory is published;
4. the trajectory server publishes position commands;
5. the online occupancy visualization changes after the first observation;
6. FUEL reports `finish exploration.`;
7. the final online occupancy PCD is saved;
8. no process crashes before completion.

Planner failure and collision-replan log counts are retained as diagnostics.
The current monitor does not claim physical collision checking against Gazebo;
the test uses FUEL's own internal safety callback.

The offline occupied-surface voxel recall is reported for map completeness.
Because some truth surfaces may be physically unobservable, this value is used
for controlled comparisons across planners and scene variants rather than as
an absolute requirement of 100 percent.

## Interpretation

A pass demonstrates a single-UAV autonomous exploration baseline on one map.
It does not prove that:

- the method is better than another planner;
- PX4 can execute the same trajectory;
- three UAVs can coordinate;
- a policy generalizes to unseen ruins.

Those claims require later controlled comparisons.
