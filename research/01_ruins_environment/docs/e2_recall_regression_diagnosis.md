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
