# Event-Driven Multi-UAV Frontier Coordination

This package is the paper's proposed coordination layer. It is intentionally
separate from FUEL: FUEL remains the mature local Frontier exploration and
trajectory-planning baseline for each UAV.

## What this core does

1. Matches current 3D Frontier clusters to persistent task IDs.
2. Marks a task resolved when the fused online map no longer reports it.
3. Reallocates only after a material Frontier or vehicle-status event. A
   configurable center-shift or information-gain threshold prevents routine
   map refreshes from causing allocation oscillation.
4. Scores complete three-UAV assignments using online information gain,
   collision-free travel cost, predicted Frontier-overlap risk, and a small
   reassignment penalty.

The allocator uses no route prior, waypoint sequence, target coordinate, or
truth PCD. A future ROS adapter must provide only online Frontier clusters and
candidate costs from each UAV's local safe planner.

## Not implemented here

- Multi-UAV simulator launch and namespaces.
- FUEL integration or any change to upstream FUEL.
- Online map fusion, Frontier extraction, or flight control.

Those interfaces must be audited before this pure coordination core is wired
to the simulator.

## Verification

Run from this directory:

```bash
python3 tests/test_cooperative_frontier_core.py
```

The tests cover persistent IDs, task resolution, unique three-UAV allocation,
overlap avoidance, and event-only reassignment.
