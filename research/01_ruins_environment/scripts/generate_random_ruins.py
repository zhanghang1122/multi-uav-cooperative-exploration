#!/usr/bin/env python3
"""Generate a reproducible randomized Ruins-Urban-01 instance."""

import argparse
import json
import re
import secrets
from dataclasses import asdict
from pathlib import Path

from generate_ruins_package import (
    VARIANTS,
    Variant,
    make_scene,
    validate_navigation,
    write_dae,
    write_model_files,
    write_mtl,
    write_obj,
    write_pcd,
    write_text_lf,
    write_world,
)


BASE = Path(__file__).resolve().parents[1]
PROFILES = {variant.key: variant for variant in VARIANTS}


def safe_asset_key(value):
    key = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if not key:
        raise ValueError("The generated scene name is empty after sanitization.")
    return key


def main():
    parser = argparse.ArgumentParser(
        description="Create a randomized but reproducible Gazebo/PCD ruins instance."
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="challenge")
    parser.add_argument("--seed", type=int, help="Fixed seed. Omit it to get a new random seed.")
    parser.add_argument("--name", help="Optional generated asset suffix.")
    parser.add_argument("--clutter-scale", type=float, default=1.0)
    parser.add_argument("--rubble", type=int)
    parser.add_argument("--columns", type=int)
    parser.add_argument("--collapsed-walls", type=int)
    parser.add_argument("--pcd-step", type=float)
    parser.add_argument("--fog", action="store_true", help="Enable the optional visual fog stressor.")
    args = parser.parse_args()

    if args.clutter_scale <= 0:
        parser.error("--clutter-scale must be greater than zero")

    template = PROFILES[args.profile]
    seed = args.seed if args.seed is not None else secrets.randbelow(2_000_000_000) + 1
    rubble = args.rubble if args.rubble is not None else round(template.rubble_count * args.clutter_scale)
    columns = args.columns if args.columns is not None else round(template.column_count * args.clutter_scale)
    collapsed = (
        args.collapsed_walls
        if args.collapsed_walls is not None
        else round(template.collapsed_wall_count * args.clutter_scale)
    )
    if min(rubble, columns, collapsed) < 0:
        parser.error("Obstacle counts cannot be negative")

    variant = Variant(
        key=args.profile,
        title=f"Randomized {template.title}",
        seed=seed,
        rubble_count=rubble,
        column_count=columns,
        collapsed_wall_count=collapsed,
        pcd_step=args.pcd_step or template.pcd_step,
        second_level_extra=template.second_level_extra,
    )
    asset_key = safe_asset_key(args.name or f"random_{args.profile}_{seed}")
    boxes = make_scene(variant)
    validation = validate_navigation(boxes, variant)
    if not validation["passed"]:
        raise RuntimeError(
            f"Generated seed {seed} failed clearance validation: {validation['blocking_edges']}"
        )

    pcd_path = BASE / "maps" / "pcd" / f"Ruins-Urban-01_{asset_key}.pcd"
    obj_path = BASE / "meshes" / "obj" / f"Ruins-Urban-01_{asset_key}.obj"
    dae_path = BASE / "meshes" / "dae" / f"Ruins-Urban-01_{asset_key}.dae"
    model_dir = BASE / "gazebo" / "models" / f"ruins_urban_01_{asset_key}"
    world_path = BASE / "gazebo" / "worlds" / f"Ruins-Urban-01_{asset_key}.world"
    validation_path = BASE / "validation" / "generated" / f"Ruins-Urban-01_{asset_key}.json"

    for target in (
        pcd_path.parent,
        obj_path.parent,
        dae_path.parent,
        model_dir,
        world_path.parent,
        validation_path.parent,
    ):
        target.mkdir(parents=True, exist_ok=True)

    write_mtl(BASE / "meshes" / "obj" / "ruins_urban_01.mtl")
    pcd_points = write_pcd(pcd_path, boxes, variant.pcd_step)
    write_obj(obj_path, boxes, "ruins_urban_01.mtl")
    write_dae(dae_path, boxes)
    write_model_files(model_dir, variant, boxes, asset_key=asset_key)
    (model_dir / "meshes").mkdir(exist_ok=True)
    (model_dir / "meshes" / dae_path.name).write_bytes(dae_path.read_bytes())
    write_world(
        world_path,
        variant,
        fog_enabled=args.fog,
        world_label=asset_key,
        model_key=asset_key,
    )

    manifest = {
        "asset_key": asset_key,
        "profile": args.profile,
        "seed": seed,
        "fog_enabled": args.fog,
        "parameters": asdict(variant),
        "box_count": len(boxes),
        "pcd_points": pcd_points,
        "pcd": str(pcd_path),
        "world": str(world_path),
        "model": str(model_dir),
        "validation": validation,
    }
    write_text_lf(validation_path, json.dumps(manifest, indent=2))

    print("Generated randomized ruins instance.")
    print(f"asset_key: {asset_key}")
    print(f"seed: {seed}")
    print(f"world: {world_path}")
    print(f"pcd: {pcd_path}")
    print("")
    print("Launch with:")
    print("  source ~/catkin_ws/devel/setup.bash")
    print('  source "$(rospack find ruins_urban_01)/setup_env.sh"')
    print(f"  roslaunch ruins_urban_01 gazebo_ruins_urban_01.launch variant:={asset_key}")


if __name__ == "__main__":
    main()
