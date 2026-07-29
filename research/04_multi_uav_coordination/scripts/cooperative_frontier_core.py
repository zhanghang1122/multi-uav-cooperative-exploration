#!/usr/bin/env python3
"""Event-driven, persistent 3D Frontier task allocation core.

This module deliberately has no ROS publishers, trajectory generator, map
reader, or truth-map dependency. A later ROS adapter will provide online
Frontier clusters and FUEL-derived collision-free path costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import sqrt
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    available: bool = True


@dataclass(frozen=True)
class FrontierObservation:
    """A Frontier cluster extracted from the current fused online map."""

    center: Point3
    information_gain: float
    radius_m: float
    reachable: bool = True


@dataclass
class PersistentFrontierTask:
    task_id: str
    center: Point3
    information_gain: float
    radius_m: float
    status: str = "available"
    assigned_vehicle: Optional[str] = None


@dataclass(frozen=True)
class AllocationConfig:
    task_matching_radius_m: float = 1.25
    material_center_shift_m: float = 0.50
    material_gain_change_ratio: float = 0.25
    gain_weight: float = 1.0
    travel_cost_weight: float = 0.45
    overlap_weight: float = 0.60
    switch_penalty: float = 0.10


@dataclass(frozen=True)
class FrontierEvent:
    event_type: str
    task_id: str


@dataclass(frozen=True)
class AllocationDecision:
    assignments: Mapping[str, Optional[str]]
    objective_score: float
    triggered: bool
    trigger_events: Sequence[FrontierEvent]


class EventDrivenFrontierCoordinator:
    """Maintains Frontier identity and assigns a non-overlapping task set.

    The exhaustive assignment search is intentional: this study has exactly
    three UAVs, so evaluating all combinations is deterministic, transparent,
    and avoids a greedy vehicle-by-vehicle allocation bias.
    """

    def __init__(self, config: AllocationConfig = AllocationConfig()) -> None:
        self._config = config
        self._tasks: Dict[str, PersistentFrontierTask] = {}
        self._assignments: Dict[str, Optional[str]] = {}
        self._next_task_number = 1
        self._pending_events: List[FrontierEvent] = []

    @property
    def tasks(self) -> Mapping[str, PersistentFrontierTask]:
        return dict(self._tasks)

    @property
    def assignments(self) -> Mapping[str, Optional[str]]:
        return dict(self._assignments)

    def observe(self, observations: Iterable[FrontierObservation]) -> List[FrontierEvent]:
        """Update persistent tasks from the current online Frontier clusters.

        A task is matched by geometric proximity. An active task that does not
        appear in a new map update is marked resolved: it may have been covered
        by another UAV or removed after reachability validation. The method does
        not infer which of those causes happened, because that distinction is
        not observable from a Frontier list alone.
        """

        incoming = list(observations)
        self._validate_observations(incoming)
        active = [task for task in self._tasks.values() if task.status in ("available", "claimed")]
        candidates: List[Tuple[float, str, int]] = []
        for task in active:
            for index, observation in enumerate(incoming):
                distance = self._distance(task.center, observation.center)
                if distance <= self._config.task_matching_radius_m:
                    candidates.append((distance, task.task_id, index))

        matched_tasks = set()
        matched_observations = set()
        events: List[FrontierEvent] = []
        for _, task_id, index in sorted(candidates):
            if task_id in matched_tasks or index in matched_observations:
                continue
            task = self._tasks[task_id]
            observation = incoming[index]
            matched_tasks.add(task_id)
            matched_observations.add(index)
            center_shift = self._distance(task.center, observation.center)
            gain_change = abs(task.information_gain - observation.information_gain) / max(
                task.information_gain, 1e-6
            )
            task.center = observation.center
            task.information_gain = observation.information_gain
            task.radius_m = observation.radius_m
            if not observation.reachable:
                task.status = "resolved"
                task.assigned_vehicle = None
                events.append(FrontierEvent("frontier_became_unreachable", task_id))
            elif (
                center_shift >= self._config.material_center_shift_m
                or gain_change >= self._config.material_gain_change_ratio
            ):
                events.append(FrontierEvent("frontier_updated", task_id))

        for task in active:
            if task.task_id not in matched_tasks:
                task.status = "resolved"
                task.assigned_vehicle = None
                events.append(FrontierEvent("frontier_resolved", task.task_id))

        for index, observation in enumerate(incoming):
            if index in matched_observations or not observation.reachable:
                continue
            task_id = "F{:03d}".format(self._next_task_number)
            self._next_task_number += 1
            self._tasks[task_id] = PersistentFrontierTask(
                task_id=task_id,
                center=observation.center,
                information_gain=observation.information_gain,
                radius_m=observation.radius_m,
            )
            events.append(FrontierEvent("frontier_created", task_id))

        self._pending_events.extend(events)
        return events

    def allocate(
        self,
        vehicles: Sequence[VehicleState],
        travel_costs: Mapping[Tuple[str, str], float],
        force: bool = False,
    ) -> AllocationDecision:
        """Return a globally scored allocation only when an event requires it.

        ``travel_costs[(vehicle_id, task_id)]`` must be supplied by a local
        collision-free planner. Missing or negative costs mean that the task is
        unavailable to that vehicle. The core therefore never assumes that a
        straight-line path through an unknown ruins is flyable.
        """

        self._validate_vehicles(vehicles)
        events = list(self._pending_events)
        unavailable = self._release_unavailable_vehicles(vehicles)
        events.extend(unavailable)
        needs_allocation = force or bool(events) or self._has_unassigned_vehicle(vehicles)
        if not needs_allocation:
            return AllocationDecision(
                assignments=dict(self._assignments),
                objective_score=0.0,
                triggered=False,
                trigger_events=tuple(),
            )

        # Existing claims remain valid candidates whenever a material event
        # triggers a new global decision. Otherwise an unrelated new Frontier
        # could accidentally make an in-progress task disappear from the plan.
        active_tasks = [task for task in self._tasks.values() if task.status in ("available", "claimed")]
        decision = self._solve_global_assignment(vehicles, active_tasks, travel_costs, events)
        self._apply_assignments(decision.assignments)
        self._pending_events = []
        return decision

    def _solve_global_assignment(
        self,
        vehicles: Sequence[VehicleState],
        tasks: Sequence[PersistentFrontierTask],
        travel_costs: Mapping[Tuple[str, str], float],
        events: Sequence[FrontierEvent],
    ) -> AllocationDecision:
        available_vehicles = [vehicle for vehicle in vehicles if vehicle.available]
        task_ids = [task.task_id for task in tasks]
        options = [None] + task_ids
        best_assignment: Dict[str, Optional[str]] = {vehicle.vehicle_id: None for vehicle in vehicles}
        best_score = 0.0
        found = False

        for proposed in product(options, repeat=len(available_vehicles)):
            selected = [task_id for task_id in proposed if task_id is not None]
            if len(selected) != len(set(selected)):
                continue
            assignment = {vehicle.vehicle_id: task_id for vehicle, task_id in zip(available_vehicles, proposed)}
            if not self._all_paths_valid(assignment, travel_costs):
                continue
            score = self._assignment_score(assignment, tasks, travel_costs)
            tie_break = tuple(assignment[vehicle.vehicle_id] or "~" for vehicle in available_vehicles)
            best_tie_break = tuple(best_assignment[vehicle.vehicle_id] or "~" for vehicle in available_vehicles)
            if not found or score > best_score or (score == best_score and tie_break < best_tie_break):
                found = True
                best_score = score
                best_assignment = {vehicle.vehicle_id: assignment.get(vehicle.vehicle_id) for vehicle in vehicles}

        return AllocationDecision(
            assignments=best_assignment,
            objective_score=best_score,
            triggered=True,
            trigger_events=tuple(events),
        )

    def _assignment_score(
        self,
        assignment: Mapping[str, Optional[str]],
        tasks: Sequence[PersistentFrontierTask],
        travel_costs: Mapping[Tuple[str, str], float],
    ) -> float:
        selected = [task_id for task_id in assignment.values() if task_id is not None]
        if not selected:
            return 0.0
        task_by_id = {task.task_id: task for task in tasks}
        max_gain = max(task.information_gain for task in tasks) or 1.0
        valid_costs = [
            cost for (vehicle_id, task_id), cost in travel_costs.items()
            if vehicle_id in assignment and task_id in task_by_id and cost >= 0.0
        ]
        max_cost = max(valid_costs) if valid_costs else 1.0
        score = 0.0
        for vehicle_id, task_id in assignment.items():
            if task_id is None:
                continue
            task = task_by_id[task_id]
            cost = travel_costs[(vehicle_id, task_id)]
            score += self._config.gain_weight * (task.information_gain / max_gain)
            score -= self._config.travel_cost_weight * (cost / max_cost)
            previous = self._assignments.get(vehicle_id)
            if previous is not None and previous != task_id:
                score -= self._config.switch_penalty

        for left_index, left_id in enumerate(selected):
            for right_id in selected[left_index + 1:]:
                score -= self._config.overlap_weight * self._overlap_risk(
                    task_by_id[left_id], task_by_id[right_id]
                )
        return score

    def _apply_assignments(self, assignments: Mapping[str, Optional[str]]) -> None:
        for task in self._tasks.values():
            if task.status == "claimed":
                task.status = "available"
                task.assigned_vehicle = None
        self._assignments = dict(assignments)
        for vehicle_id, task_id in assignments.items():
            if task_id is None:
                continue
            task = self._tasks[task_id]
            task.status = "claimed"
            task.assigned_vehicle = vehicle_id

    def _release_unavailable_vehicles(self, vehicles: Sequence[VehicleState]) -> List[FrontierEvent]:
        available_by_id = {vehicle.vehicle_id: vehicle.available for vehicle in vehicles}
        events: List[FrontierEvent] = []
        for task in self._tasks.values():
            owner = task.assigned_vehicle
            if owner is not None and not available_by_id.get(owner, False):
                task.status = "available"
                task.assigned_vehicle = None
                self._assignments[owner] = None
                events.append(FrontierEvent("vehicle_became_unavailable", task.task_id))
        return events

    def _has_unassigned_vehicle(self, vehicles: Sequence[VehicleState]) -> bool:
        return any(vehicle.available and vehicle.vehicle_id not in self._assignments for vehicle in vehicles)

    @staticmethod
    def _all_paths_valid(
        assignment: Mapping[str, Optional[str]],
        travel_costs: Mapping[Tuple[str, str], float],
    ) -> bool:
        return all(
            task_id is None or (vehicle_id, task_id) in travel_costs and travel_costs[(vehicle_id, task_id)] >= 0.0
            for vehicle_id, task_id in assignment.items()
        )

    @staticmethod
    def _distance(first: Point3, second: Point3) -> float:
        return sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))

    @classmethod
    def _overlap_risk(cls, first: PersistentFrontierTask, second: PersistentFrontierTask) -> float:
        combined_radius = first.radius_m + second.radius_m
        if combined_radius <= 0.0:
            return 0.0
        return max(0.0, 1.0 - cls._distance(first.center, second.center) / combined_radius)

    @staticmethod
    def _validate_observations(observations: Sequence[FrontierObservation]) -> None:
        for observation in observations:
            if observation.information_gain < 0.0:
                raise ValueError("information_gain must be non-negative")
            if observation.radius_m <= 0.0:
                raise ValueError("radius_m must be positive")

    @staticmethod
    def _validate_vehicles(vehicles: Sequence[VehicleState]) -> None:
        vehicle_ids = [vehicle.vehicle_id for vehicle in vehicles]
        if len(vehicle_ids) != len(set(vehicle_ids)):
            raise ValueError("vehicle IDs must be unique")
