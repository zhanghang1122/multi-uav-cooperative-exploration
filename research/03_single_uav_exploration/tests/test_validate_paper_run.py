#!/usr/bin/env python3

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "validate_paper_run.py"


def load_script():
    spec = importlib.util.spec_from_file_location("validate_paper_run", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_csv(path, columns):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow({column: "1" for column in columns})


class ValidatePaperRunTest(unittest.TestCase):
    def test_complete_formal_run_passes(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "run_manifest.yaml").write_text(
                json.dumps(
                    {
                        "run_class": "formal",
                        "prior_route_allowed": False,
                        "truth_map_usage": "offline_evaluation_only",
                    }
                ),
                encoding="utf-8",
            )
            (root / "runtime.json").write_text(
                json.dumps({"passed": True}), encoding="utf-8"
            )
            for filename, columns in module.CSV_COLUMNS.items():
                write_csv(root / filename, sorted(columns))
            for filename in ("events.jsonl", "planner_rosout.jsonl"):
                (root / filename).write_text('{"event":"test"}\n', encoding="utf-8")
            for filename in (
                "final_occupancy.pcd",
                "software_versions.txt",
                "notes.md",
            ):
                (root / filename).write_text("evidence\n", encoding="utf-8")
            self.assertEqual(module.validate_run(root), [])

    def test_debug_run_is_rejected_as_formal(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            errors = module.validate_run(root)
            self.assertIn("missing run_manifest.yaml", errors)


if __name__ == "__main__":
    unittest.main()
