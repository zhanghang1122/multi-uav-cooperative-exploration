# Reproducibility Protocol

## Required Run Metadata

Every experiment must record:

- UTC timestamp;
- Git commit SHA;
- method and configuration name;
- world profile and seed;
- UAV count and initial poses;
- sensor topics and parameters;
- exploration bounds and stopping condition;
- simulated duration and wall-clock duration;
- success, collision, coverage, path, allocation, and runtime metrics.

## Seed Split

Use `config/benchmark_seeds.yaml` as the initial declaration:

- development seeds may be used for debugging and parameter selection;
- test seeds must remain unseen until all method parameters are frozen;
- fixed benchmark worlds are used for paired method comparisons;
- failed seeds must not be silently removed.

## Fair Comparison

For each paired trial, all methods must use:

- the same generated world file;
- the same initial poses;
- the same UAV dynamics and collision geometry;
- the same sensors, noise, range, and update frequency;
- the same exploration bounds and completion threshold;
- the same CPU allocation and simulator clock definition.

Use simulated time for primary task duration when Gazebo's real-time factor differs across runs.

## Versioning

Before paper submission:

1. freeze the experiment configuration;
2. commit all code and manifests;
3. create a signed or annotated `v1.0.0` tag;
4. publish a GitHub Release;
5. archive that release with Zenodo;
6. cite the release DOI in the manuscript.

The paper must state which commit or release produced each table.
