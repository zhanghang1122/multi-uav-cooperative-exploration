# Blender Python source model for Ruins-Urban-01.
# Run inside Blender:
#   blender --background --python generate_ruins_urban_01_blender.py
#
# This script imports the generated scene JSON and creates editable named boxes.
# It can export OBJ/DAE and save a .blend source file when Blender is available.

import json
import math
import os
from pathlib import Path

import bpy

BASE = Path(__file__).resolve().parents[1]
SCENE_JSON = BASE / "config" / "scene_geometry.json"

with SCENE_JSON.open("r", encoding="utf-8") as f:
    data = json.load(f)

VARIANT = os.environ.get("RUINS_VARIANT", "complex")
if VARIANT not in data["geometry"]:
    raise ValueError(f"Unknown RUINS_VARIANT={VARIANT!r}; choose one of {sorted(data['geometry'])}")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

materials = {}
palette = {
    "concrete": (0.58, 0.56, 0.52, 1.0),
    "concrete_light": (0.68, 0.66, 0.61, 1.0),
    "dark_concrete": (0.35, 0.35, 0.34, 1.0),
    "rebar": (0.12, 0.12, 0.12, 1.0),
    "rubble": (0.46, 0.42, 0.36, 1.0),
    "brick": (0.43, 0.29, 0.23, 1.0),
    "soil": (0.29, 0.25, 0.20, 1.0),
    "rust": (0.37, 0.20, 0.13, 1.0),
    "hazard": (0.65, 0.18, 0.12, 1.0),
}
for name, color in palette.items():
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    materials[name] = mat

for box in data["geometry"][VARIANT]:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=box["center"])
    obj = bpy.context.object
    obj.name = box["name"]
    obj.dimensions = box["size"]
    obj.rotation_euler = box["rpy"]
    obj.data.materials.append(materials.get(box["material"], materials["concrete"]))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Add lights/camera only for inspection. They are not used by PCD generation.
bpy.ops.object.light_add(type="AREA", location=(0, 0, 7.5))
light = bpy.context.object
light.name = "inspection_area_light"
light.data.energy = 700
light.data.size = 18

bpy.ops.object.camera_add(location=(0, -43, 22), rotation=(math.radians(62), 0, 0))
bpy.context.scene.camera = bpy.context.object

blend_path = BASE / "blender" / f"Ruins-Urban-01_{VARIANT}_source.blend"
blend_path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

bpy.ops.wm.obj_export(filepath=str(BASE / "meshes" / "obj" / f"Ruins-Urban-01_{VARIANT}.obj"))
try:
    bpy.ops.wm.collada_export(filepath=str(BASE / "meshes" / "dae" / f"Ruins-Urban-01_{VARIANT}.dae"))
except Exception:
    pass
