# Stage 2: Base-Stack Reproducibility Gate

## Purpose

This gate decides whether the stock FUEL single-UAV baseline can be used as a
paper baseline in the fixed E2 benchmark. It is not a performance experiment.
It must be passed before collecting a five-run G0 or B1 table.

## Required evidence

1. Regenerate E2 from the fixed generator and create a FUEL overlay.
2. Run `audit_fuel_overlay_contract.py`. It must report the exact horizontal
   bounds and the indoor vertical bounds `0.80 m <= z <= 2.05 m` in the
   official FUEL algorithm include.
3. Execute one position-neutral exploration run. No route, target coordinate,
   room label, branch label, or truth map may enter FUEL.
4. Run `validate_flight_envelope.py` on the recorder trajectory. It must show
   zero height violations with the declared tolerance.
5. The recorder must produce `trial_summary.json` and
   `runtime_diagnostics.json`, with one of three explicit outcomes:
   `fuel_reported_finish`, `planner_stall`, or `runtime_failure`.

## Decision rule

- `fuel_reported_finish` plus zero height violations: the baseline is eligible
  for formal repeated trials.
- `planner_stall`: preserve the evidence as G0 baseline failure; do not rerun
  it until a separate proposed recovery method is specified and tested.
- missing recorder artifacts, simulator abort, or RViz failure: integration
  failure. Repair the launch chain; it is not an algorithm result.

## Why this gate exists

The E2 geometry contract prevents over-wall shortcuts only if the online
planner is actually confined to the declared indoor band. Separating launch
configuration, trajectory compliance, and planner outcome prevents an
incomplete or unstable run from being presented as autonomous-exploration
performance.
