# Base Trial: Uniform Height Boundary

## Purpose

This trial is the first completed autonomous FUEL run on
`Ruins-Urban-01_base`. It used the original uniform exploration height
`0.35-7.65 m`. The result is retained as a diagnostic baseline for comparison
with the later variant-specific height boundary.

## Scientific Boundary

The planner received only:

- the initial pose `[-19.2, 0.0, 1.35]`;
- the rectangular exploration bounds;
- online local sensor observations.

It received no obstacle layout, prior occupancy map, target coordinate,
waypoint sequence, patrol route, or manual region partition. The simulator
truth PCD was available only to the local sensor renderer.

## Recorded Result

| Metric | Value |
|---|---:|
| Runtime validation | passed |
| FUEL finish detected | yes |
| Finish time | 1116.965 s |
| Monitor duration | 1119.092 s |
| Estimated path length | 1257.497 m |
| B-spline messages | 1139 |
| Position command messages | 111559 |
| Maximum occupied points | 62273 |
| Saved final occupied points | 62169 |
| Planning failure logs | 0 |
| Collision replan logs | 6 |

Final map:

```text
/tmp/ruins_fuel_base_final.pcd
size: 1.8 MB
sha256: ee0578e1e23da311105c9be07be52c69f4120b0b6eee8ab1b22a9f3a21e5857d
```

## Interpretation

The run proves that FUEL can autonomously complete the scene and save an online
3D occupancy result without a predefined route. It does not yet prove that the
search volume is well specified.

The path is roughly ten times the environment's 125.36 m reference navigation
graph length. The `base` geometry reaches only 3.877 m and contains no vertical
connector, while this trial allowed the UAV center to search up to 7.65 m.
Consequently, the trial likely spent substantial time clearing unknown free
space above the intended lower navigation layer.

The next controlled trial changes only the legal vertical search bound to
`0.35-2.65 m`. All FUEL algorithm parameters, the scene PCD, initial pose, and
horizontal bounds remain unchanged. Comparing completion time, path length,
final map coverage, and collision replans isolates the effect of correctly
specifying the task volume.
