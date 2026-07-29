# Research Modules

This directory contains the implementation stages of the paper. Each stage
must be independently reproducible before the next stage is presented as a
completed result.

| Stage | Scope | Current status |
|---|---|---|
| `01_ruins_environment` | Parameterized 3D ruins, exports, and geometry validation | Implemented and structurally validated |
| `02_mapping_baseline` | Common 3D occupancy-map interface and mapping metrics | Planned, not yet created |
| `03_single_uav_exploration` | Single-UAV FUEL Frontier baseline and independent map evaluation | Implemented and runtime-validated |
| `04_multi_uav_coordination` | Event-driven persistent-Frontier allocation core | Implemented and unit-tested; simulator integration is not started |
| `05_experiments` | Comparisons, ablations, random-seed trials, and statistics | Planned, not yet created |

Planned directories are listed only as a roadmap. They will be created when
working code, configuration, a test procedure, and evidence are available.
