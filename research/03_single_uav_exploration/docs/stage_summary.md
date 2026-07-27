# Stage 03 Summary: FUEL Single-UAV Exploration

## Purpose

This stage adds an online frontier-driven exploration decision loop after the
stationary Stage 02 interface check. Its purpose is to establish a repeatable
single-UAV autonomous baseline before multi-UAV task allocation is introduced.

## Literature Decision

The publisher-recommended papers on the first page of the reviewed Chinese
paper concern bio-inspired formation control and target search. They are useful
background but do not define the unknown-space mapping problem. FUEL is used as
the executable baseline because it explicitly integrates incremental frontier
maintenance, hierarchical viewpoint planning, and minimum-time trajectories.
TARE supplies the local/global hierarchy rationale; RACER and GVP-MREP define
the later multi-UAV comparison space.

## Implemented Components

- non-destructive FUEL launch overlay generation;
- fixed Ruins-Urban-01 PCD selection;
- safety-inset exploration bounds and validated entrance pose;
- input and output SHA-256 manifest;
- position-neutral one-shot start signal after odometry is available;
- runtime evidence for occupancy growth, B-splines, commands, path length,
  planner diagnostics, and FUEL's finish state;
- fixed-map and unseen-seed experiment protocol.

## Scientific Boundary

The PCD is simulator truth and is only consumed by FUEL's local sensing node.
The exploration planner does not receive a prior map. The generated overlay
retains upstream FUEL algorithm parameters and does not modify the FUEL
checkout.

This stage does not integrate PX4, does not use three UAVs, and is not a novel
exploration algorithm. Its role is to supply the control condition against
which the later coordination method is evaluated.

## Evidence Status

The overlay unit test, Python syntax, ROS XML, package metadata, environment
paths, and non-modification invariant can be checked on the Windows host.
Actual ROS topics, occupancy growth, trajectory execution, completion, and
virtual-machine timing require Ubuntu 20.04 runtime trials.
