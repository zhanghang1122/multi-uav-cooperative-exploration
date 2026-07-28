#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "summarize_trial_repeats.py"


def load_script():
    spec = importlib.util.spec_from_file_location("repeat_summary", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepeatSummaryTest(unittest.TestCase):
    def test_summary_never_selects_a_best_run(self):
        module = load_script()
        result = module.summarize([10.0, 12.0])
        self.assertEqual(result["mean"], 11.0)
        self.assertEqual(result["minimum"], 10.0)
        self.assertEqual(result["maximum"], 12.0)
        self.assertAlmostEqual(result["coefficient_of_variation_percent"], 12.8565)


if __name__ == "__main__":
    unittest.main()
