#!/usr/bin/env python3
"""Apply or restore the B1-R reachable-frontier recovery patch to FUEL.

Stock FUEL returns FAIL when the online-selected frontier viewpoint has no
geometric A* path. Its state machine then selects the same view again on the
next planning cycle. B1-R first retries the other online-generated frontier
viewpoints from that same cycle and selects the shortest collision-free A*
path. It also keeps the narrow recovery for a later kinodynamic seed failure.

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

STOCK_GEOMETRIC_BLOCK = """  planner_manager_->path_finder_->reset();
  if (planner_manager_->path_finder_->search(pos, next_pos) != Astar::REACH_END) {
    ROS_ERROR("No path to next viewpoint");
    return FAIL;
  }
  ed_->path_next_goal_ = planner_manager_->path_finder_->getPath();
"""

REACHABLE_GEOMETRIC_BLOCK = """  planner_manager_->path_finder_->reset();
  if (planner_manager_->path_finder_->search(pos, next_pos) != Astar::REACH_END) {
    // The tour-selected view is unreachable in the current online inflated
    // map. Re-evaluate only other views generated from this same frontier set.
    double best_length = 1e100;
    int best_id = -1;
    vector<Eigen::Vector3d> best_path;
    for (int i = 0; i < ed_->points_.size(); ++i) {
      if ((ed_->points_[i] - next_pos).norm() < 1e-3) continue;
      planner_manager_->path_finder_->reset();
      if (planner_manager_->path_finder_->search(pos, ed_->points_[i]) == Astar::REACH_END) {
        vector<Eigen::Vector3d> candidate_path = planner_manager_->path_finder_->getPath();
        const double candidate_length = Astar::pathLength(candidate_path);
        if (candidate_length < best_length) {
          best_length = candidate_length;
          best_id = i;
          best_path = candidate_path;
        }
      }
    }
    if (best_id < 0) {
      ROS_ERROR("B1-R: no reachable viewpoint in current online frontier set");
      return FAIL;
    }
    next_pos = ed_->points_[best_id];
    next_yaw = ed_->yaws_[best_id];
    ed_->refined_points_ = { next_pos };
    ed_->refined_views_ = { next_pos + 2.0 * Vector3d(cos(next_yaw), sin(next_yaw), 0) };
    ed_->path_next_goal_ = best_path;
    ROS_WARN("B1-R reachable-frontier recovery: selected alternate online viewpoint %d", best_id);
  } else {
    ed_->path_next_goal_ = planner_manager_->path_finder_->getPath();
  }
  // A reachable fallback may change the desired view yaw.
  diff = fabs(next_yaw - yaw[0]);
  time_lb = min(diff, 2 * M_PI - diff) / ViewNode::yd_;
"""

STOCK_KINODYNAMIC_BLOCK = """      // Search kino path to exactly next viewpoint and optimize
      std::cout << \"Mid goal\" << std::endl;
      ed_->next_goal_ = next_pos;
      if (!planner_manager_->kinodynamicReplan(
              pos, vel, acc, ed_->next_goal_, Vector3d(0, 0, 0), time_lb))
        return FAIL;
"""

LEGACY_RECOVERY_BLOCK = """      // Search kino path to exactly next viewpoint and optimize.
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

RECOVERY_BLOCK = """      // Search kino path to exactly next viewpoint and optimize.
      // If the kinodynamic seed search fails after the geometric A* path has
      // already been verified, preserve autonomy by executing a short prefix
      // of that online path. This mirrors stock FUEL's far-goal local-horizon
      // branch and avoids optimizing a long path across an unseen corner.
      std::cout << "Mid goal" << std::endl;
      ed_->next_goal_ = next_pos;
      if (!planner_manager_->kinodynamicReplan(
              pos, vel, acc, ed_->next_goal_, Vector3d(0, 0, 0), time_lb)) {
        ROS_WARN("B1-R recovery: kinodynamic seed failed; use local geometric A* prefix");
        const double recovery_horizon = 2.5;
        double recovery_len = 0.0;
        vector<Eigen::Vector3d> recovery_path = { ed_->path_next_goal_.front() };
        for (int i = 1; i < ed_->path_next_goal_.size() && recovery_len < recovery_horizon; ++i) {
          auto cur_pt = ed_->path_next_goal_[i];
          recovery_len += (cur_pt - recovery_path.back()).norm();
          recovery_path.push_back(cur_pt);
        }
        ed_->next_goal_ = recovery_path.back();
        planner_manager_->planExploreTraj(recovery_path, vel, acc, time_lb);
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

    if REACHABLE_GEOMETRIC_BLOCK in text and RECOVERY_BLOCK in text:
        return "already_applied", backup
    if REACHABLE_GEOMETRIC_BLOCK in text and LEGACY_RECOVERY_BLOCK in text:
        if not dry_run:
            source.write_text(text.replace(LEGACY_RECOVERY_BLOCK, RECOVERY_BLOCK, 1), encoding="utf-8", newline="\n")
        return "upgraded", backup
    if REACHABLE_GEOMETRIC_BLOCK in text and STOCK_KINODYNAMIC_BLOCK in text:
        if not dry_run:
            source.write_text(text.replace(STOCK_KINODYNAMIC_BLOCK, RECOVERY_BLOCK, 1), encoding="utf-8", newline="\n")
        return "upgraded_kinodynamic", backup
    if STOCK_GEOMETRIC_BLOCK in text and RECOVERY_BLOCK in text:
        if not backup.exists():
            raise RuntimeError(
                "A legacy B1-R mid-goal patch was found without its original-source backup. "
                "No source file was changed. Restore or inspect the FUEL checkout first."
            )
        if not dry_run:
            source.write_text(text.replace(STOCK_GEOMETRIC_BLOCK, REACHABLE_GEOMETRIC_BLOCK, 1), encoding="utf-8", newline="\n")
        return "upgraded_reachability", backup
    if STOCK_GEOMETRIC_BLOCK not in text or STOCK_KINODYNAMIC_BLOCK not in text:
        raise RuntimeError(
            "The verified stock or recognized B1-R source blocks were not found. No source file was changed. "
            "Use --restore if this checkout was previously patched, or inspect the FUEL version first."
        )
    action = "applied"
    if backup.exists():
        if source.read_bytes() != backup.read_bytes():
            raise RuntimeError(
                "A B1-R backup already exists, but the current stock source does not match that backup. "
                "No source file was changed. Inspect both files before applying B1-R."
            )
        action = "reapplied_after_restore"
    if not dry_run:
        if not backup.exists():
            backup.write_bytes(source.read_bytes())
        patched = text.replace(STOCK_GEOMETRIC_BLOCK, REACHABLE_GEOMETRIC_BLOCK, 1)
        source.write_text(patched.replace(STOCK_KINODYNAMIC_BLOCK, RECOVERY_BLOCK, 1), encoding="utf-8", newline="\n")
    return action, backup


def restore_patch(source, dry_run):
    backup = Path(str(source) + BACKUP_SUFFIX)
    if not backup.exists():
        raise RuntimeError("No B1-R backup exists beside the FUEL source; nothing was restored.")
    text = source.read_text(encoding="utf-8")
    if REACHABLE_GEOMETRIC_BLOCK not in text or RECOVERY_BLOCK not in text:
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
        "method_id": "B1R_fuel_reachable_frontier_recovery",
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
                "When stock FUEL's online-selected viewpoint has no geometric A* path, evaluate only "
                "the remaining current-cycle online frontier viewpoints and select the shortest "
                "collision-free path. When the later mid-goal kinodynamic seed fails after a geometric "
                "path succeeds, generate a trajectory from a 2.5 m prefix of that online path."
            ),
        },
    }
    if not args.dry_run:
        write_manifest(workspace / MANIFEST_NAME, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
