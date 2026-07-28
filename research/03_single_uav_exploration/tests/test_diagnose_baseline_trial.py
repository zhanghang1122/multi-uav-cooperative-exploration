#!/usr/bin/env python3

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "diagnose_baseline_trial.py"


def load_script():
    spec = importlib.util.spec_from_file_location("baseline_diagnosis", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BaselineDiagnosisTest(unittest.TestCase):
    def test_debug_completion_is_not_called_an_algorithm_judgement(self):
        module = load_script()
        artifacts = {"passed": True}
        runtime = {"passed": True}
        manifest = {"run_class": "debug"}
        classification, recommendations = module.classify(
            artifacts, runtime, manifest, {"last_window_recall_gain": 0.0}
        )
        self.assertEqual(classification, "debug_or_calibration_only")
        self.assertTrue(any("not a formal" in item for item in recommendations))

    def test_coverage_summary_reports_final_window_gain(self):
        module = load_script()
        rows = [
            {"elapsed_s": "0", "surface_recall": "0", "surface_precision": "0", "surface_f1": "0"},
            {"elapsed_s": "60", "surface_recall": "0.4", "surface_precision": "0.8", "surface_f1": "0.5"},
            {"elapsed_s": "120", "surface_recall": "0.6", "surface_precision": "0.75", "surface_f1": "0.666"},
        ]
        summary = module.summarize_coverage(rows)
        self.assertEqual(summary["final_surface_recall"], 0.6)
        self.assertEqual(summary["last_window_recall_gain"], 0.2)


if __name__ == "__main__":
    unittest.main()
