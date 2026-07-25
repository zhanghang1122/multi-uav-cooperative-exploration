# Environment Generation

## Source of Truth

`scripts/generate_ruins_package.py` is the deterministic source of the fixed benchmark assets.
`scripts/generate_random_ruins.py` creates additional parameterized instances from the same geometry rules.
`scripts/generate_ruins_urban_01_blender.py` imports the generated scene description into Blender for visual editing.

Generated runtime representations:

- PCD for FUEL, RACER, MARSIM, and point-cloud simulators;
- DAE and OBJ for platform-neutral mesh use;
- SDF models and world files for Gazebo Classic;
- JSON validation manifests for reproducibility.

## Parameterization

The vehicle collision diameter is `D = 0.65 m`. Corridor widths are constrained by:

```text
normal corridor   = max(2.50, 3.8 D)
narrow corridor   = max(1.35, 2.1 D)
vertical connector = max(2.00, 3.1 D)
```

Randomized profiles inherit the fixed profile's rubble, column, collapsed-wall, PCD-resolution, and second-level settings.
The random seed controls placement and orientation. Optional command-line parameters override obstacle counts without
changing the structural corridor graph.

## Fixed and Random Worlds

Fixed worlds are immutable benchmark instances:

```text
base    seed 240701
medium  seed 240702
complex seed 240703
```

Random worlds test generalization. A random world is identified by profile and seed, for example
`random_complex_574240941`. The generator writes the exact parameters and validation result to a JSON manifest.

## Fog

Fog is disabled in all primary geometry experiments. Enabling fog changes perception difficulty and must be evaluated as a
separate factor with a declared sensor model.

## Ground-Truth Isolation

The generator uses a reference graph only to confirm intended connectivity and clearance. Runtime exploration nodes must
not subscribe to or load:

- `config/scene_geometry.json`;
- `config/complexity_metrics.json`;
- validation JSON files;
- the complete PCD or mesh as a prior map.

These files may be used only by the simulator and offline evaluation.
