# Literature Anchors for Protocol V2

Only peer-reviewed journal articles with a verifiable DOI are used as anchors
for the current protocol. These references are not a claim that their code or
environment has been copied; each entry states the limited element adopted.

1. Zhou, B., Zhang, Y., Chen, X., & Shen, S. (2021). FUEL: Fast UAV
   Exploration Using Incremental Frontier Structure and Hierarchical Planning.
   *IEEE Robotics and Automation Letters, 6*(2), 779--786.
   https://doi.org/10.1109/LRA.2021.3051563
   - Adopted: incremental Frontier bookkeeping and the separation of global
     coverage, local viewpoints and dynamically feasible flight trajectories.
   - Not adopted: any claim that the stock single-UAV implementation is a
     multi-UAV coordination algorithm.

2. Senarathne, P. G. C. N., & Wang, D. (2015). Incremental algorithms for
   safe and reachable Frontier detection for robot exploration. *Robotics and
   Autonomous Systems, 72*, 189--206.
   https://doi.org/10.1016/j.robot.2015.05.009
   - Adopted: safe and reachable Frontier detection as a separate condition
     before a candidate may influence exploration decisions.
   - Scope note: the paper is 2D ground-robot work; V2 tests the same
     principle with the 3D inflated free-space/motion-planning contract, not a
     claim of reproducing the paper unchanged.

3. Bayer, J., & Faigl, J. (2026). Decentralized multi-robot exploration under
   low-bandwidth communications. *Autonomous Robots, 50*, Article 7.
   https://doi.org/10.1007/s10514-025-10234-3
   - Adopted: a clean separation between coordination and navigation;
     repeated trials; comparison of exploration time, travelled distance,
     coverage and communication; and conventional Hungarian/MinPos/MTSP-style
     allocation baselines.
   - Not adopted: the low-bandwidth-only Cross-rank policy as the primary
     method, because V2's initial study intentionally tests shared-map
     cooperation before communication deprivation.

4. Peng, X. (2024). An autonomous Unmanned Aerial Vehicle exploration platform
   with a hierarchical control method for post-disaster infrastructures.
   *IET Cyber-Systems and Robotics, 6*, e12107.
   https://doi.org/10.1049/csy2.12107
   - Adopted: constrained post-disaster/infrastructure scenes, online
     next-best-view decision making, collision avoidance and explicit mapping
     completeness/accuracy evaluation.
   - Not adopted: structural-damage inspection as an extra task; V2 stops at
     cooperative exploration and geometry mapping.

5. Amigoni, F., et al. (2026). Estimating map completeness in robot
   exploration. *Autonomous Robots, 50*, Article 1.
   https://doi.org/10.1007/s10514-025-10221-8
   - Adopted: distinguish a planner's internal stop event from map
     completeness, and assess coverage progress explicitly.
   - Not adopted: the paper's CNN stopping predictor; V2 uses fixed offline
     surface-recall thresholds for fair evaluation.

## Supporting Source-Verification Notes

- FUEL's official university record identifies it as a 2021 IEEE Robotics and
  Automation Letters article and describes its incremental Frontier information
  structure and hierarchical planning.
- The ScienceDirect record for Senarathne and Wang states that valid frontiers
  are safe and reachable boundary contours maintained incrementally.
- The publisher record for Bayer and Faigl documents a repeated-trial
  comparison of coordination methods, navigation/coordination separation, and
  the role of maps, waypoints and positions in allocation.

These notes are deliberately modest. Any additional algorithm, quantitative
claim or environment parameter must be verified against a cited source before
it enters the protocol.
