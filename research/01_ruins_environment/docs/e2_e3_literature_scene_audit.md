# E2/E3 Literature-Grounded Scene Review

## Status

**The current E2/E3 assets are retired from the formal paper protocol.** They
pass only a limited static reachability check. That check establishes neither a
meaningful three-UAV coordination challenge nor journal-quality environmental
complexity. They may be retained as generator smoke tests, but no B1/B2/B3/P
result from them may be presented as a paper comparison result.

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

## What the Current Assets Do Not Establish

The current E2 has a `42 x 32 x 4.2 m` envelope. Its volume is comparable to
the `20 x 80 x 3 m` FUEL maze, but volume alone is not a complexity argument.
The current branch-anchor distances are approximately `20.2 m`, `20.0 m` and
`41.6 m`. This produces an avoidable two-to-one workload imbalance before a
coordination method has made any decision. It would confound an experiment
whose claim is better task allocation among three UAVs.

Further, its declared narrow passages are `1.6--2.0 m`, or roughly
`4.0--5.0 D_eff` for the active FUEL envelope (`D_eff = 0.398 m`). They are
safe and useful for an interface test, but do not by themselves test constrained
navigation. Its large open central area, sparse local occluders and few
overhead elements also make the exploration burden visually and topologically
weaker than a damaged-building main benchmark should be. The current E3 has the
same issue in a different layout. Neither asset may be described as matching a
published benchmark merely because it contains rooms, walls and boxes.

There is also no defensible journal rule such as "N rooms plus M obstacles is
complex". Published environments are designed around a hypothesis: FUEL uses
cluttered rooms, a bridge and a long maze to expose planning/visibility limits;
the distributed three-UAV study uses city and forest scenes and finds that a
third UAV only helps when the environment has sufficient spatial complexity.
Consequently, this project must quantify *its own* controlled topology,
visibility and clearance characteristics rather than copy arbitrary object
counts.

## V2 Design Basis Before Any New Simulation

The next assets must be designed and accepted as a controlled benchmark suite,
not as a collection of visually different rooms. The values below are project
acceptance criteria derived to test the stated cooperative-exploration claim;
they are not falsely presented as mandatory values from a single paper.

### Common Runtime Contract

- One fixed geometry and fixed sensor/control profile are used for all B1, B2,
  B3 and P trials on E2.
- The online system receives only its local sensor data, current pose estimate
  and the prescribed bounded exploration volume. It receives no route,
  waypoint list, room label, static graph, branch assignment or truth map.
- Every declared topology/visibility/clearance value is an offline audit only.
- The same FUEL collision envelope is used for scene validation and execution.
  With the current profile this is `D_eff = 0.398 m`.
- All externally reported map quality remains an offline comparison between the
  generated ground-truth PCD and the final online map.

### E2-V2: Fixed Primary Cooperative-Exploration Scene

E2-V2 is a one-storey, partially damaged public/industrial building. It does
not claim a hidden second floor. Its complexity must arise from a common
entry, obstructed visibility, alternative routes, loops, terminal pockets and
three concurrently discoverable workload regions.

The design target is:

- a short entry foyer that prevents immediate line-of-sight access to all
  branches;
- three entry-reachable wings with comparable entry-to-frontier route scales
  (target spread no greater than 25% before online allocation);
- at least two local choices per wing, at least one terminal pocket per wing,
  and multiple cross-wing alternatives so that revisits and allocation choices
  are consequential;
- a mixture of wide (`>= 2.0 m`), normal (`1.2--1.6 m`) and challenging
  (`0.9--1.2 m`) physical clearances, all validated after inflation. A
  challenging clearance remains greater than about `2.3 D_eff`; no
  non-flyable decorative bottleneck is permitted;
- structural columns, partial walls, equipment groups and damage clusters
  distributed across all wings. Each object class must create either occlusion,
  a route choice, or a local sensing challenge; purely decorative clutter is
  prohibited; and
- partial-height/overhead damage only where it changes three-dimensional
  sensing or path choice and where the associated free space is physically
  reachable. It must not create a fictitious upper floor.

The E2-V2 audit must publish:

- reachable-volume fraction at the configured planning envelope;
- route-length distribution to three branch anchors, including its spread;
- offline topology-contract node/edge count, junction count, cycle rank and
  terminal count, with every declared node/edge verified against inflated
  geometry;
- physical clearance distribution and the number of verified passages in each
  clearance class relative to `D_eff`;
- initial sensor-visibility audit from the launch pose, plus per-wing occlusion
  and obstacle-role counts; and
- geometry role counts and physical/inflated occupied-footprint fraction.

### E3-V2: Fixed Generalization Scene

E3-V2 retains the same sensor model, planning envelope and comparable total
size, but has a deliberately different topology: a constrained service spine,
asymmetric side bays, rack/damage occlusion and unequal branch lengths. It is
not used to tune P. It is used after P is frozen to test whether the B3/P
difference persists outside E2's balanced three-wing structure. It must pass
the same offline reachability, clearance, topology and visibility audits.

## Implementation Gate

No scene-generation code is changed again until an E2-V2/E3-V2 parameter
table and an audit algorithm have been reviewed together. The next code change
must generate both scenes and the exact offline audit reports described above.
Only after visual inspection and sensor-interface validation may E2-V2 enter
the five-repeat B1 baseline protocol.

## Experimental Rule After Redesign

1. Regenerate, visually inspect and retain the accepted E2-V2/E3-V2 validation
   reports with the exact platform profile used.
2. Run B1 five times on the approved E2.
3. Run B2, B3 and P five times each on the identical E2 asset and settings.
4. After P is frozen, run the required comparative generalization experiment on
   E3. Truth maps remain offline evaluation inputs only throughout.

No route, target point, room label, graph, task list or truth map may be
supplied to the online exploration planner in any stage.
