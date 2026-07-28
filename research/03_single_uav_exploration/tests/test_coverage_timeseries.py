#!/usr/bin/env python3

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = STAGE_ROOT / "scripts" / "evaluate_coverage_timeseries.py"


def load_script():
    spec = importlib.util.spec_from_file_location("coverage_timeseries", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoverageTimeseriesTest(unittest.TestCase):
    def test_series_tracks_recall_and_precision_over_time(self):
        module = load_script()
        truth = {(0, 0, 0), (2, 0, 0)}
        observed = {
            (0, 0, 0): 1.0,
            (9, 9, 9): 3.0,
        }
        rows = module.compute_series(truth, observed, tolerance=0, interval_s=1.0)

        at_two_seconds = next(row for row in rows if row["elapsed_s"] == 2.0)
        final = rows[-1]
        self.assertEqual(at_two_seconds["surface_recall"], 0.5)
        self.assertEqual(at_two_seconds["surface_precision"], 1.0)
        self.assertEqual(final["surface_recall"], 0.5)
        self.assertEqual(final["surface_precision"], 0.5)

    def test_first_seen_reader_applies_bounds(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "first_seen.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    ("voxel_x", "voxel_y", "voxel_z", "first_seen_s")
                )
                writer.writerow((0, 0, 5, 1.0))
                writer.writerow((30, 0, 5, 2.0))
            observed = module.read_first_seen(
                path,
                bounds=[-1.0, -1.0, 0.0, 1.0, 1.0, 1.0],
                resolution=0.1,
            )
            self.assertEqual(observed, {(0, 0, 5): 1.0})


if __name__ == "__main__":
    unittest.main()
