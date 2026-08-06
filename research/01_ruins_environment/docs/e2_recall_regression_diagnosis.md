# E2 Recall regression diagnosis

Date: 2026-08-05

## Question

Why did E2 surface Recall fall from approximately 0.90 in the legacy runs to
0.124 in `G0_E2_rep01`?

## Evidence timeline

| Run | Scene/reference | Runtime contract | Duration (s) | Path (m) | Truth voxels | Observed voxels | Recall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| E1 five-run pilot | E1 interior reference | easier pilot scene | 200.5-256.7 | 233.0-243.7 | 101,252 | 154,861-158,564 | 0.8721-0.8753 |
| E2 interface check | E2 sparse interior reference | `virtual_ceil_height=-10` | 746.578 | 686.373 | 244,273 | 543,655 | 0.903624 |
| E2 legacy rep01 | E2 sparse interior reference | `virtual_ceil_height=-10` | 710.757 | 731.472 | 244,273 | 491,041 | 0.896202 |
| B1R legacy verify | E2 sparse interior reference | legacy recovery experiment | 742.707 | 752.293 | 244,273 | 476,181 | 0.894536 |
| G0 E2 rep01 | E2 dense interior reference | common height envelope; virtual ceiling at 1.85 m | 331.252 | 400.098 | 470,331 after mask | 53,594 after mask | 0.124004 |

The E1 five-run result is a pilot on a different, smaller scene and is not an
E2 comparator. The three legacy E2 runs used a different truth-reference
density and did not enforce the indoor no-wall-overflight contract.

## Confirmed causes

### 1. The truth denominator changed

E2 surface sampling was changed from 0.14 m to 0.07 m while evaluation remained
at 0.10 m voxel resolution. The old truth contained 244,273 voxels; the current
raw truth contains 478,935 voxels, an increase of 96.06 percent. The old Recall
and current Recall therefore do not share the same denominator and must not be
placed in one formal comparison table.

This correction exposes surface cells that the old source lattice skipped. It
does not by itself explain the entire drop: even the current run's 58,323
matched truth voxels would cover only 23.88 percent of the old denominator.

### 2. The legacy high-Recall runs violated the final indoor contract

Archived launch output records `sdf_map/virtual_ceil_height=-10` for the legacy
stack. The vehicle could rise above internal partitions, which was also observed
visually. Those runs acquired broad line of sight by bypassing the intended
doorway and corridor topology. Their approximately 0.90 Recall is useful as a
pilot and an ablation of the height constraint, but it is not an admissible
indoor-navigation baseline.

### 3. The constrained stock planner terminated before covering E2

After the artificial virtual-ceiling layer is masked, `G0_E2_rep01` retains
53,594 physical observed voxels and 53,558 of them match truth. Precision is
0.999328, so the local mapper is not the source of the Recall collapse.

The runtime trace is decisive:

- at 318.999, 319.369, and 319.680 s: `No path to next viewpoint`;
- the remaining Frontier count then falls from two to one;
- at 327.953 s: `No coverable frontier`;
- at 327.977 s: `finish exploration`.

Stock FUEL therefore treated locally infeasible remaining work as completion.
The run ended after 331.252 s and 400.098 m, versus approximately 711-743 s and
731-752 m in the legacy high-Recall E2 runs.

### 4. The virtual ceiling polluted the raw map output

The raw G0 map contains 180,086 voxels. Of these, 126,492 (70.24 percent) belong
to the artificial virtual-ceiling layer. That layer is a planner boundary, not
physical geometry. Evaluator schema 2 masks the same layer from truth and every
observed snapshot before physical-map scoring. Unmasked Precision/F1 values are
diagnostic only.

## Interpretation

The current result does not mean that the depth mapper recognizes walls poorly.
It means:

1. mapped physical surfaces are geometrically accurate (Precision 0.999328);
2. the vehicle visits too little of the valid environment (Recall 0.124004);
3. stock FUEL's Frontier termination and local reachability handling fail under
   the final indoor constraint.

This is the failure mode that the reachability-aware method must address.
However, the current interior reference only checks that a surface has free air
immediately beside it. It does not yet prove that a collision-free sensor pose
exists within the flight band and sensor model. Formal repeated runs remain
blocked until a method-independent coverable-surface reference audit is frozen.

## Data status

- E1 five-run data: retained as pilot/reproducibility evidence only.
- Legacy E2 data near 0.90 Recall: retained as height-constraint ablation and
  debugging evidence only.
- `G0_E2_rep01`: retained as a valid runtime diagnostic; do not delete or rerun.
- No G0 five-run summary is produced until the coverable-reference gate passes.

## Next gate

Create and audit a frozen E2 coverable-surface reference using only offline
geometry, the common flight band, vehicle clearance, sensor range/FOV, and
line-of-sight constraints. It must be method-independent and must never enter
online planning. Then rescore all retained E2 maps against that same reference
before starting `G0_E2_rep02`.

The gate is implemented by `build_e2_coverable_surface_reference.py`. Its
defaults reproduce the stock FUEL sensing contract used by this repository:
0.199 m obstacle inflation, 0.5--4.5 m useful ray range, and 0.56125 rad
vertical half-FOV. Candidate sensor poses are generated only in collision-free,
entry-reachable airspace below the common virtual-ceiling guard. Visibility is
checked against the fixed box geometry. The script has no ROS publishers and
does not accept a trajectory, online map, Frontier topic, room label, goal, or
route.

### Method basis

- Zhou et al., *FUEL: Fast UAV Exploration Using Incremental Frontier
  Structure and Hierarchical Planning*, IEEE Robotics and Automation Letters,
  2021, DOI: [10.1109/LRA.2021.3051563](https://doi.org/10.1109/LRA.2021.3051563).
  This is the journal source for the baseline planner; numerical sensor and
  inflation defaults are taken from its public implementation used here.
- Saska et al., *Cooperative Unmanned Aerial System Reconnaissance in a
  Complex Urban Environment and Uneven Terrain*, Sensors, 2019, DOI:
  [10.3390/s19173754](https://doi.org/10.3390/s19173754). The paper treats a
  point as visible only when it is inside sensor range and has unobstructed
  visual line of sight.
- Kladnik et al., *Autonomous Full 3D Coverage Using an Aerial Vehicle...*,
  Robotics, 2024, DOI:
  [10.3390/robotics13060083](https://doi.org/10.3390/robotics13060083). Its
  coverage denominator is based on visible map nodes and its analysis uses
  sensor FOV and ray casting. This supports separating physical surface Recall
  from geometrically coverable surface Recall.

```bash
ASSETS=/tmp/coop_building_e2_primary

rosrun ruins_urban_01 build_e2_coverable_surface_reference.py \
  --truth-pcd "$ASSETS/pcd/Coop-Building-E2-Primary-Damaged-Interior_interior_reference.pcd" \
  --output-pcd "$ASSETS/pcd/Coop-Building-E2-Primary-Damaged-Interior_coverable_reference.pcd" \
  --noncoverable-pcd "$ASSETS/pcd/Coop-Building-E2-Primary-Damaged-Interior_noncoverable_reference.pcd" \
  --output-json "$ASSETS/validation/Coop-Building-E2-Primary-Damaged-Interior_coverable_reference.json"
```

For fixed E2-v5 assets, the verified default gate has these golden counts:

| Audit item | Expected value |
| --- | ---: |
| Raw interior-reference voxels | 478,935 |
| Physical truth after equal virtual-ceiling mask | 470,331 |
| Geometrically coverable truth voxels | 371,320 |
| Non-coverable truth voxels | 99,011 |
| Coverable fraction of physical truth | 0.789487 |
| Entry-reachable sensor-pose lattice cells | 83,252 |

The corresponding deterministic PCD hashes are:

- coverable reference: `05918d347fd821a47e558f75c46c373206473ea3e8ae6c4095aacf4453651f3d`;
- non-coverable reference: `bec99eeae44f2cd20f3e08bc08b9e93dbae0d0727d3ca3f38138438b243c4415`.

Any mismatch means the generated assets, script revision, or parameters differ;
do not combine that run with the frozen E2 comparison table.

Both physical-surface Recall and coverable-surface Recall remain reportable.
The former diagnoses how much of the complete model was reconstructed; the
latter is the fair exploration score under the frozen vehicle/sensor contract.
ICP-aligned scores remain diagnostic only and must not replace either primary
score.

Rescore a retained run without changing its map or trajectory:

```bash
RUN=$HOME/uav_experiment_results/G0_E2_rep01
REFERENCE=$ASSETS/pcd/Coop-Building-E2-Primary-Damaged-Interior_coverable_reference.pcd

rosrun ruins_urban_01 evaluate_surface_map.py \
  --truth-pcd "$REFERENCE" \
  --observed-pcd "$RUN/final_online_occupancy.pcd" \
  --snapshots-csv "$RUN/snapshots.csv" \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --virtual-ceiling-z-m 1.85 \
  --output "$RUN/map_quality_coverable.json"
```

Before changing a planner parameter, localize the retained run's missed
coverage with the same virtual-ceiling mask as the global score:

```bash
RUN=$HOME/uav_experiment_results/G0_E2_rep01
TRUTH=/tmp/coop_building_e2_primary/pcd/Coop-Building-E2-Primary-Damaged-Interior_interior_reference.pcd

rosrun ruins_urban_01 diagnose_e2_branch_coverage.py \
  --truth-pcd "$TRUTH" \
  --observed-pcd "$RUN/final_online_occupancy.pcd" \
  --trajectory-csv "$RUN/trajectory.csv" \
  --resolution-m 0.1 \
  --tolerance-voxels 1 \
  --virtual-ceiling-z-m 1.85 \
  --output "$RUN/branch_coverage.json"
```

This report is post-hoc only. Its region masks are never passed to the online
planner. A region with few trajectory samples and low Recall indicates an
exploration/reachability failure; many trajectory samples with low Recall
instead points to the sensor/reference contract and must not be treated as the
same failure.
