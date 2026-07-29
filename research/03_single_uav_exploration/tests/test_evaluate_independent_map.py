import importlib.util
import pathlib
import sys
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "evaluate_independent_map.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("evaluate_independent_map", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IndependentMapEvaluationTests(unittest.TestCase):
    def test_surface_metrics_reports_symmetric_match_quality(self):
        metrics = MODULE.surface_metrics([(0, 0, 0), (1, 0, 0)], [(0, 0, 0), (3, 0, 0)], 0.1, 0)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(metrics["f1"], 0.5)

    def test_bounds_validation_rejects_reversed_axes(self):
        with self.assertRaises(ValueError):
            MODULE.parse_bounds([1, 0, 0, 0, 1, 1])
