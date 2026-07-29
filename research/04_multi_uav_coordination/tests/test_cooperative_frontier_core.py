#!/usr/bin/env python3
import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "cooperative_frontier_core.py"
SPEC = importlib.util.spec_from_file_location("cooperative_frontier_core", MODULE_PATH)
CORE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CORE
SPEC.loader.exec_module(CORE)


class CooperativeFrontierCoreTest(unittest.TestCase):
    def setUp(self):
        self.vehicles = [CORE.VehicleState("uav1"), CORE.VehicleState("uav2"), CORE.VehicleState("uav3")]

    def test_spatial_matching_preserves_a_task_identity(self):
        coordinator = CORE.EventDrivenFrontierCoordinator()
        coordinator.observe([CORE.FrontierObservation((1.0, 2.0, 1.5), 10.0, 1.0)])
        first_id = next(iter(coordinator.tasks))
        coordinator.observe([CORE.FrontierObservation((1.2, 2.0, 1.5), 12.0, 1.0)])
        self.assertEqual(list(coordinator.tasks), [first_id])
        self.assertEqual(coordinator.tasks[first_id].information_gain, 12.0)

    def test_resolved_frontier_releases_its_owner(self):
        coordinator = CORE.EventDrivenFrontierCoordinator()
        coordinator.observe([CORE.FrontierObservation((1.0, 0.0, 1.0), 10.0, 1.0)])
        task_id = next(iter(coordinator.tasks))
        coordinator.allocate(self.vehicles, {("uav1", task_id): 1.0}, force=True)
        events = coordinator.observe([])
        self.assertIn(CORE.FrontierEvent("frontier_resolved", task_id), events)
        self.assertEqual(coordinator.tasks[task_id].status, "resolved")
        self.assertIsNone(coordinator.tasks[task_id].assigned_vehicle)

    def test_assignment_is_unique_across_three_uavs(self):
        coordinator = CORE.EventDrivenFrontierCoordinator()
        coordinator.observe([
            CORE.FrontierObservation((0.0, 0.0, 1.0), 9.0, 1.0),
            CORE.FrontierObservation((8.0, 0.0, 1.0), 9.0, 1.0),
            CORE.FrontierObservation((16.0, 0.0, 1.0), 9.0, 1.0),
        ])
        task_ids = sorted(coordinator.tasks)
        costs = {
            ("uav1", task_ids[0]): 1.0, ("uav1", task_ids[1]): 8.0, ("uav1", task_ids[2]): 16.0,
            ("uav2", task_ids[0]): 8.0, ("uav2", task_ids[1]): 1.0, ("uav2", task_ids[2]): 8.0,
            ("uav3", task_ids[0]): 16.0, ("uav3", task_ids[1]): 8.0, ("uav3", task_ids[2]): 1.0,
        }
        decision = coordinator.allocate(self.vehicles, costs)
        self.assertEqual(set(decision.assignments.values()), set(task_ids))

    def test_overlap_penalty_selects_separated_frontiers(self):
        config = CORE.AllocationConfig(travel_cost_weight=0.0, overlap_weight=1.0)
        coordinator = CORE.EventDrivenFrontierCoordinator(config)
        coordinator.observe([
            CORE.FrontierObservation((0.0, 0.0, 1.0), 10.0, 5.0),
            CORE.FrontierObservation((1.0, 0.0, 1.0), 10.0, 5.0),
            CORE.FrontierObservation((20.0, 0.0, 1.0), 8.5, 1.0),
        ])
        task_ids = sorted(coordinator.tasks)
        costs = {(vehicle.vehicle_id, task_id): 1.0 for vehicle in self.vehicles[:2] for task_id in task_ids}
        decision = coordinator.allocate(self.vehicles[:2], costs)
        selected = set(task_id for task_id in decision.assignments.values() if task_id is not None)
        self.assertIn(task_ids[2], selected)
        self.assertNotEqual(selected, {task_ids[0], task_ids[1]})

    def test_without_an_event_existing_assignments_are_held(self):
        coordinator = CORE.EventDrivenFrontierCoordinator()
        coordinator.observe([CORE.FrontierObservation((0.0, 0.0, 1.0), 10.0, 1.0)])
        task_id = next(iter(coordinator.tasks))
        first = coordinator.allocate(self.vehicles, {("uav1", task_id): 1.0})
        second = coordinator.allocate(self.vehicles, {("uav1", task_id): 99.0})
        self.assertTrue(first.triggered)
        self.assertFalse(second.triggered)
        self.assertEqual(first.assignments, second.assignments)

    def test_material_frontier_change_triggers_a_new_decision(self):
        coordinator = CORE.EventDrivenFrontierCoordinator()
        coordinator.observe([CORE.FrontierObservation((0.0, 0.0, 1.0), 10.0, 1.0)])
        task_id = next(iter(coordinator.tasks))
        costs = {("uav1", task_id): 1.0}
        coordinator.allocate(self.vehicles, costs)
        self.assertEqual(coordinator.observe([CORE.FrontierObservation((0.1, 0.0, 1.0), 10.0, 1.0)]), [])
        self.assertFalse(coordinator.allocate(self.vehicles, costs).triggered)
        events = coordinator.observe([CORE.FrontierObservation((0.8, 0.0, 1.0), 10.0, 1.0)])
        self.assertIn(CORE.FrontierEvent("frontier_updated", task_id), events)
        self.assertTrue(coordinator.allocate(self.vehicles, costs).triggered)


if __name__ == "__main__":
    unittest.main()
