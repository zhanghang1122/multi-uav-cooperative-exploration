# Complex-Environment Literature Comparison and V2 Decision Record

## Purpose

This document prevents the scene from being justified by appearance alone. It
records what relevant peer-reviewed work actually uses, what can be transferred
to a three-UAV cooperative-exploration study, and what must remain a project
engineering decision.

## Representative Sources

| Source | Environment strategy | Measurements connected to the environment | Transfer to this project |
| --- | --- | --- | --- |
| Zhou et al., FUEL, IEEE RA-L 2021 | Bridge volume, `20 x 80 x 3 m` maze, cluttered indoor test volumes; low initial visibility and different room structures | Exploration time, travelled distance, exploration progression; repeated trials from the same initial condition | Use a bounded unknown volume, fixed start, sensor-limited online exploration, and a mix of topology/occlusion rather than obstacle count alone. |
| Yan et al., Drones 2024 | Two qualitatively different environments (city and forest), one/two/three UAV teams | Completion time, path length, coverage, exploration rate and path efficiency; five trials per configuration | Use E2 as one fixed primary scene and E3 as a topology-different post-freeze generalization scene. A third UAV must be tested where concurrent work is meaningful. |
| Gui et al., Drones 2023 | Bounded unknown 3-D space, depth sensing and OctoMap updated online | Coverage efficiency and redundancy under decentralized multi-UAV allocation | Never pre-divide the runtime map. Let frontier/task candidates arise online from sensed free/unknown boundaries. |
| Liu et al., UBES, Software Impacts 2023 | Parameterized building generator with robot/sensor/communication variations and randomization | Strategy comparison, task assignment, loss and sensing conditions | Keep a fixed exact scene for fair B1/B2/B3/P comparison; use controlled random variants only as a later robustness study. |

Sources: [FUEL](https://doi.org/10.1109/LRA.2021.3051563),
[FUEL manuscript](https://repository.hkust.edu.hk/ir/bitstream/1783.1-108720/1/033635_1.pdf),
[distributed frontier/NBV exploration](https://doi.org/10.3390/drones8110630),
[decentralized multi-UAV exploration](https://doi.org/10.3390/drones7060337),
and [UBES](https://doi.org/10.1016/j.simpa.2023.100576).

## Direct Comparison Against Retired E2-V1

| Question | Retired E2-V1 candidate | Literature-supported requirement | Decision |
| --- | --- | --- | --- |
| Is its physical size sufficient? | `42 x 32 x 4.2 m`, comparable in volume to a published FUEL maze | Size may be useful, but no source treats volume alone as complexity | Keep a comparable scale; do not use it as an acceptance claim. |
| Are there fair three-UAV workloads? | Branch-anchor lengths near `20.2`, `20.0`, `41.6 m` | Team-scaling comparisons need common deployment conditions and a scene where simultaneous work can matter | Reject. Redesign E2 with comparable initial branch workload. |
| Is constrained navigation tested? | Declared throats `1.6--2.0 m`, about `4--5 D_eff` | Published scenes mix open and constrained structures; collision constraints must be executable | Reject as sufficient. Use a clearance distribution, then validate after inflation. |
| Does the scene hide information initially? | Large central open area, sparse occlusion | FUEL's indoor/maze settings deliberately use partial observation and low initial visibility | Reject as sufficient. Add a restricted foyer and wing-local occluders. |
| Does it support generalization? | E3 differs visually but its challenge is not quantified | Published multi-environment studies change environment class/topology, not merely object count | Reject as sufficient. E3-V2 must have an audited different topology. |

## Final Experimental Interpretation

There is no valid claim that an algorithm is better simply because it completes
one dense-looking room. The required claim is narrower and testable:

> In a bounded, initially unknown damaged-building environment, does coordinated
> allocation reduce redundant exploration and time-to-coverage while preserving
> map completeness and safety, relative to equal hardware/sensing baselines?

E2-V2 is designed to answer this comparison fairly. E3-V2 answers whether the
result survives a topology change. A later controlled random suite answers
robustness; it does not replace repeated experiments on the same fixed asset.

## What Is Not Taken From Literature as a Fake Requirement

The exact number of walls, boxes, rooms, turns or rubble objects is not copied
from a paper because the reviewed papers do not prescribe universal counts.
Those numbers will be reported transparently as this project's design
parameters, together with the resulting topology, clearance, visibility and
reachability audits. This is more reproducible than claiming an arbitrary
object count is a journal standard.
