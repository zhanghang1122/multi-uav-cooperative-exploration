# Historical Demo Archive

This directory preserves the useful, verified parts of three earlier UAV
simulation exercises. Each demo is isolated because the software stacks and
claims are different.

| Demo | Scope | Evidence level | Public status |
|---|---|---|---|
| `demo01_d435i_perception` | P230 + D435i sensor and obstacle perception | Topic frequency, screenshots, and video evidence | Partial baseline |
| `demo02_ego_swarm_10uav` | Ten-agent EGO-Swarm planning with `fake_drone` dynamics | Completed visual run and trigger record | Reproducible wrapper |
| `demo03_fuel_exploration` | Single-UAV unknown-space exploration with FUEL | Completed visual run and map-growth record | Official baseline wrapper |

The archive does not claim that all three demos use PX4 or Gazebo:

- Demo 1 uses the Prometheus/PX4/Gazebo perception chain, but its later
  D435i-to-world TF flight attempt was not verified as successful.
- Demo 2 is the upstream EGO-Swarm lightweight simulation. Its default
  `fake_drone` model is not a PX4 flight-dynamics model.
- Demo 3 is the upstream FUEL simulator. It is not the unfinished
  FUEL-to-Prometheus/PX4 bridge.

See [`docs/demo_audit.md`](../docs/demo_audit.md) for the acceptance decisions.

