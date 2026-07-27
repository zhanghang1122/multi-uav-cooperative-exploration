# Research Modules

This directory contains the implementation stages of the paper. Each stage
must be independently reproducible before the next stage is presented as a
completed result.

| Stage | Scope | Current status |
|---|---|---|
| `01_ruins_environment` | Parameterized 3D ruins, exports, and geometry validation | Implemented and structurally validated |
| `02_mapping_baseline` | MARSIM local sensing and online OctoMap interface | Implementation ready; Ubuntu runtime validation pending |
| `03_single_uav_exploration` | Single-UAV exploration baseline in the ruins | Planned, not yet created |
| `04_multi_uav_coordination` | Three-UAV cooperative allocation and navigation | Planned, not yet created |
| `05_experiments` | Comparisons, ablations, random-seed trials, and statistics | Planned, not yet created |

Stage 02 includes code, configuration, and a test procedure, but is not marked
experimentally complete until its Ubuntu-generated runtime report passes.
