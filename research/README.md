# Research Modules

This directory contains the implementation stages of the paper. Each stage
must be independently reproducible before the next stage is presented as a
completed result.

| Stage | Scope | Current status |
|---|---|---|
| `01_ruins_environment` | Parameterized 3D ruins, exports, and geometry validation | Implemented and structurally validated |
| `02_mapping_baseline` | MARSIM local sensing and online OctoMap interface | Implementation ready; Ubuntu runtime validation pending |
| `03_single_uav_exploration` | Official FUEL single-UAV exploration adapter | Implementation ready; Ubuntu runtime validation pending |
| `04_multi_uav_coordination` | Three-UAV cooperative allocation and navigation | Planned, not yet created |
| `05_experiments` | Comparisons, ablations, random-seed trials, and statistics | Planned, not yet created |

Stages 02 and 03 include code, configuration, and test procedures, but neither
is marked experimentally complete until its Ubuntu-generated runtime reports
pass. Stage 03 must not be used to hide an unresolved Stage 02 sensing failure.
