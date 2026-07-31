# E2/E3 Literature-Grounded Scene Audit

## Status

**E2 and E3 from the current generator are candidate assets only. They are not
approved for formal B1/B2/B3/P paper experiments.** Do not start E2 trials
until the acceptance criteria in this document are verified from generated
assets.

## What the Literature Supports

There is no journal rule such as a mandatory number of rooms, corridors or
boxes. A defensible scene must instead support the study claim and make the
claim reproducible:

1. **Unknown bounded 3-D exploration, not a supplied route.** FUEL evaluates a
   bridge volume and a large maze, repeats each method from the same initial
   configuration, and measures time and distance. Its real indoor tests also
   use clutter, low initial visibility and rooms of different structure.
   [Zhou et al., 2021](https://doi.org/10.1109/LRA.2021.3051563).
2. **A main comparison environment and a different generalization environment.**
   A distributed multi-UAV journal study evaluates one-, two- and three-UAV
   teams in two distinct environments, with five simulations per configuration
   and common deployment conditions.
   [Drones, 2024, 8(11), 630](https://doi.org/10.3390/drones8110630).
3. **The environment must make coordination consequential.** RACER develops
   decentralized allocation to keep UAVs exploring distinct regions while
   balancing workload under limited communication. Therefore a three-UAV main
   scene must expose several concurrent, initially unknown branches after a
   common entry; merely increasing the number of walls is insufficient.
   [Zhou et al., 2023](https://doi.org/10.1109/TRO.2023.3236945).
4. **Complexity has geometric and topological aspects.** FUEL's published
   large-maze benchmark is `20 x 80 x 3 m`, while its field tests combine
   obstacle clutter, low visibility and room transitions. Scene complexity is
   not represented by volume alone.
   [FUEL accepted manuscript](https://repository.hkust.edu.hk/ir/bitstream/1783.1-108720/1/033635_1.pdf).

## Audit Result for the Current Candidate

The current E2 has a suitable *scale* for a main scene: `42 x 32 x 4.2 m`
(about `5645 m^3`), comparable to the `4800 m^3` FUEL large-maze benchmark.
Its generated geometry is also nontrivial: 51 wall segments, 7 columns, 9
equipment obstacles, 6 damage objects and 4 partial overhead elements.

However, it is **not yet paper-ready** because these key quantities are only
design labels, not independently derived from the navigable geometry:

- number of rooms, junctions, loops and dead ends;
- width distribution and count of clearance-critical passages;
- number of independently reachable exploration branches after the common
  entry;
- topological difference between E2 and E3;
- density/occlusion measurements that explain why E2 is harder than E1.

The existing 100% reachability test proves that the current collision geometry
is connected for the configured FUEL envelope. It does **not** prove that the
scene creates a meaningful three-UAV coordination challenge.

## Frozen Redesign Requirements

### E2: Primary Damaged-Building Comparison Scene

E2 must be a connected damaged indoor building with one common launch area and
three initially unknown, concurrently reachable wings. Each wing must contain
occlusion and at least one local decision; two or more cross-connections must
create loops; terminal pockets must create dead-end decisions. Damage, columns
and equipment must be structural causes of visibility loss or path choices, not
random visual clutter. Partial overhead elements may be used for 3-D sensing
occlusion, but no inaccessible second floor may be claimed.

The generated E2 validation report must derive and publish:

- reachable-volume fraction at the configured planning envelope;
- free-space graph node/edge count, junction count, cycle count and terminal
  count, extracted from a declared flight-slice graph;
- physical passage-width distribution and the number of passages in each
  clearance band relative to `D_eff`;
- count of entry-reachable major branches and branch workload proxies;
- geometry role counts and occupied-volume ratio.

### E3: Topology-Generalization Scene

E3 must retain the same sensor model, planning envelope and comparable scale,
but use a different topology rather than simply adding more obstacles. The
target is an asymmetric service/workshop structure: a long constrained spine,
side rooms, rack-induced occlusion and unequal branch lengths. It must pass the
same validation and must not be used to tune P. E3 evaluates whether B3/P
performance is robust to a topology different from E2.

## Experimental Rule After Redesign

1. Validate and visually inspect the redesigned E2/E3 reports.
2. Run B1 five times on the approved E2.
3. Run B2, B3 and P five times each on the identical E2 asset and settings.
4. After P is frozen, run the required comparative generalization experiment on
   E3. Truth maps remain offline evaluation inputs only throughout.

No route, target point, room label, graph, task list or truth map may be
supplied to the online exploration planner in any stage.
