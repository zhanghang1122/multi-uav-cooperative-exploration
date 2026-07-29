import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "record_single_uav_trial.py"
SPEC = importlib.util.spec_from_file_location("record_single_uav_trial", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordSingleUavTrialTests(unittest.TestCase):
    def test_voxelize_deduplicates_and_discards_invalid_points(self):
        voxels = MODULE.voxelize_points([(0.1000001, 0.2, 0.3), (0.1, 0.2, 0.3), (float("nan"), 0, 0)], 0.1)
        self.assertEqual(len(voxels), 1)

    def test_write_ascii_pcd_has_valid_header_and_sorted_points(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "map.pcd"
            MODULE.write_ascii_pcd(path, [(2, 0, 0), (1, 0, 0)])
            lines = path.read_text(encoding="ascii").splitlines()
        self.assertIn("POINTS 2", lines)
        self.assertEqual(lines[-2:], ["1.000000 0.000000 0.000000", "2.000000 0.000000 0.000000"])

    def test_invalid_sampling_parameters_are_rejected(self):
        with self.assertRaises(SystemExit):
            MODULE.parse_arguments(["--output-dir", "/tmp/x", "--map-resolution-m", "0"])

    def test_distance_xyz(self):
        self.assertEqual(MODULE.distance_xyz((0, 0, 0), (3, 4, 0)), 5.0)
