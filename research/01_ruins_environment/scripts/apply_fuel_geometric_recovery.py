#!/usr/bin/env python3
"""Apply or restore the B1-R geometric-path recovery patch to a FUEL checkout.

The verified FUEL branch first finds a geometric A* path to a selected
frontier viewpoint.  For mid-range goals it subsequently tries a kinodynamic
A* seed; stock FUEL returns FAIL when that second search fails, even though
the geometric path has already been accepted.  B1-R retains stock FUEL's
online frontier selection and map, but falls back to its existing
waypoints-to-B-spline path generator in that precise case.

This tool changes one exact upstream code block, creates a sibling backup,
and writes a manifest with SHA-256 values.  It never changes a launch file,
map, route, goal, sensor stream, or planner parameter.
"""

from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path


RELATIVE_SOURCE = Path(
    "src/FUEL/fuel_planner/exploration_manager/src/fast_exploration_manager.cpp"
)
BACKUP_SUFFIX = ".b1r_original"
MANIFEST_NAME = "fuel_b1r_geometric_recovery_manifest.json"

STOCK_BLOCK = """      // Search kino path to exactly next viewpoint and optimize
      std::cout << \"Mid goal\" << std::endl;
      ed_->next_goal_ = next_pos;
      if (!planner_manager_->kinodynamicReplan(
              pos, vel, acc, ed_->next_goal_, Vector3d(0, 0, 0), time_lb))
        return FAIL;
"""

RECOVERY_BLOCK = """      // Search kino path to exactly next viewpoint and optimize.
      // If the kinodynamic seed search fails after the geometric A* path has
      // already been verified, preserve autonomy by using that online path as
      // the trajectory seed. This is the same generator used by stock FUEL
      // for its near and far goal branches.
      std::cout << \"Mid goal\" << std::endl;
      ed_->next_goal_ = next_pos;
      if (!planner_manager_->kinodynamicReplan(
              pos, vel, acc, ed_->next_goal_, Vector3d(0, 0, 0), time_lb)) {
        ROS_WARN(\"B1-R recovery: kinodynamic seed failed; use validated geometric A* path\");
        planner_manager_->planExploreTraj(ed_->path_next_goal_, vel, acc, time_lb);
      }
"""


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def apply_patch(source, dry_run):
    text = source.read_text(encoding="utf-8")
    backup = Path(str(source) + BACKUP_SUFFIX)

    if RECOVERY_BLOCK in text:
        return "already_applied", backup
    if STOCK_BLOCK not in text:
        raise RuntimeError(
            "The verified stock FUEL mid-goal block was not found. No source file was changed. "
            "Use --restore if this checkout was previously patched, or inspect the FUEL version first."
        )
    if backup.exists():
        raise RuntimeError(
            "A B1-R backup already exists but the source is neither recognized stock nor recognized patched. "
            "No source file was changed."
        )
    if not dry_run:
        backup.write_bytes(source.read_bytes())
        source.write_text(text.replace(STOCK_BLOCK, RECOVERY_BLOCK, 1), encoding="utf-8", newline="\n")
    return "applied", backup


def restore_patch(source, dry_run):
    backup = Path(str(source) + BACKUP_SUFFIX)
    if not backup.exists():
        raise RuntimeError("No B1-R backup exists beside the FUEL source; nothing was restored.")
    text = source.read_text(encoding="utf-8")
    if RECOVERY_BLOCK not in text:
        raise RuntimeError(
            "The active source does not contain the recognized B1-R block. No source file was changed."
        )
    if not dry_run:
        source.write_bytes(backup.read_bytes())
    return "restored", backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuel-workspace", required=True, help="Catkin workspace containing src/FUEL.")
    parser.add_argument("--restore", action="store_true", help="Restore the exact backup made during apply.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing files.")
    args = parser.parse_args()

    workspace = Path(args.fuel_workspace).expanduser().resolve()
    source = workspace / RELATIVE_SOURCE
    if not source.is_file():
        raise SystemExit("FUEL source not found: {}".format(source))

    sha_before = sha256(source)
    action, backup = restore_patch(source, args.dry_run) if args.restore else apply_patch(source, args.dry_run)
    sha_after = sha256(source)
    manifest = {
        "schema_version": 1,
        "method_id": "B1R_fuel_geometric_path_recovery",
        "action": action,
        "dry_run": args.dry_run,
        "fuel_workspace": str(workspace),
        "source": str(source),
        "backup": str(backup),
        "sha256_before": sha_before,
        "sha256_after": sha_after,
        "runtime_contract": {
            "route_prior_used": False,
            "goal_prior_used": False,
            "truth_map_usage": "offline_evaluation_only",
            "recovery_rule": (
                "Only after stock FUEL's geometric A* path to the online-selected viewpoint succeeds "
                "and its mid-goal kinodynamic seed search fails, generate a trajectory from that existing "
                "online geometric path."
            ),
        },
    }
    if not args.dry_run:
        write_manifest(workspace / MANIFEST_NAME, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
