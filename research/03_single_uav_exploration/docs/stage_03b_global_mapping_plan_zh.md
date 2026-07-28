# 阶段 03B：自主前沿探索与独立全局建图的集成计划

## 已冻结的事实

在 `Ruins-Urban-01_base` 的两个 P0 校准试验中，FUEL 都在没有人工路线、航点、目标坐标或先验障碍地图的条件下完成探索。它接收的仅是初始位姿、允许搜索的三维边界和在线传感器观测。

两次试验的最终静态占据点云表面召回率分别为 `0.609835` 和
`0.607915`，均值为 `0.608875`；完成时间均值为 `335.716 s`，路径长度均值为 `438.107 m`。重复性良好，但最终重建质量不足以作为论文正式的单机对比组。

本阶段不把该问题归因于“无人机没有自主探索”。FUEL 已产生约 415 次在线重规划并以 `No coverable frontier` 结束。更合理的工程判断是：FUEL 的 `sdf_map/occupancy_all` 服务于前沿规划，不能未经验证地被当成最终三维重建产品。

## 文献依据与边界

本阶段不是临时把一个建图器叠到 FUEL 上，而是遵循以下三类已有研究的模块化逻辑：

1. **自主探索决策。** Zhou 等提出的 FUEL 在地图被传感器更新后增量更新
   frontier，再依次计算全局探索访问顺序、局部视点和安全轨迹；无 frontier 时
   才终止探索。当前项目将 FUEL 限定为单机自主探索基线，而非本文创新
   [1]。
2. **传感器与算法的解耦验证。** Kong 等的 MARSIM 以点云环境和当前 LiDAR
   位姿渲染观测，并通过 ROS 接口连接定位、规划和控制模块。其论文还给出
   了 FUEL 在室内点云场景中的自主探索示例 [2]。因此，本项目必须核对真实
   点云话题、传感器坐标系和 TF，而不能根据节点名称猜测接口。
3. **三维占据建图。** Hornung 等的 OctoMap 以八叉树概率模型表达三维占据
   空间，是将运动传感器观测累积为独立全局地图的成熟基线 [3]。本阶段选用
   它作为可解释的重建输出，而不将其声称为新方法。

由此得到的工程原则是：**规划器和最终重建器可以共享在线观测，但其输入、
输出与评价必须可分离审计。** 这是当前项目为避免“用规划内部地图替代重建
结论”而采用的实验控制措施，不宣称为任何文献的原创算法。

## 需要保持的研究边界

```text
FUEL 前沿规划器
  输入：在线局部传感器、初始位姿、搜索边界
  输出：在线选择的视点和无碰撞轨迹

独立全局建图器
  输入：同一在线传感器数据 + 在线位姿/TF
  输出：独立的全局 OctoMap / 最终点云
```

两条链路共享观测，但互不向对方提供人工目标、航点或环境真值。场景真值 PCD 仍只进入 FUEL 的局部传感器渲染器；试验结束后才用于离线评价。

因此，新增全局建图器不会把实验变为“指定路线建图”，也不会改变论文的自主导航主题。

## 为什么暂停使用轨迹可见性代理

P0 两条轨迹的简化距离/稀疏点云视线代理均接近 `1.0`，但该代理不建模真实 LiDAR 视场、遮挡连续体、噪声和可达空间。在 42 m x 32 m 的 base 场景中，约 438 m 的长路径足以使该指标饱和，无法区分算法优劣。

该代理仅保留为调试材料，不进入论文的表格、图或结论。正式评价仍使用：

- 最终静态点云相对于场景真值的 Precision、Recall 和 F1；
- 覆盖率随时间变化曲线；
- 完成时间、路径长度、重规划次数和规划耗时；
- 重复试验的均值、标准差和成功率。

## 03B 的实施顺序

1. 从**生成后的 FUEL overlay**提取真实节点和显式 ROS remap，不根据节点名称猜测点云接口。
2. 在一次不计入论文的短运行中，确认点云话题的消息类型、`frame_id`，以及 `world -> sensor` 变换是否存在。
3. 仅当输入点云处于传感器坐标系、且对应 TF 存在时，接入 `octomap_server`。这样 OctoMap 才能正确使用运动中的传感器原点进行射线更新。
4. 记录独立 mapper 的全局占据图并导出最终 PCD；与 FUEL 规划占据图并列保存，不替换、不混淆。
5. 先进行一次 03B 集成验证：确认自主 FUEL 仍完成、独立地图持续增长、坐标系无错误。
6. 只有 03B 成功后才重新运行 P1 base 正式重复试验；在此之前不进入 medium、complex 或三机。

### 当前已确认的静态接口

生成后的 overlay 已确认 FUEL 探索器订阅：

```text
/pcl_render_node/cloud        点云观测
/pcl_render_node/sensor_pose  传感器在世界坐标中的位姿
/state_ukf/odom               飞行器里程计
```

这只证明 launch 配置的重映射关系，尚未证明点云消息的实际 `frame_id`。
启动 FUEL 后，在另一个终端执行下列只读审计器：

```bash
rosrun ruins_single_uav_exploration fuel_mapping_interface_probe.py \
  --output /tmp/ruins_fuel_overlay/base/runtime_mapping_interface.json
```

它最多等待 20 秒，记录三条话题的首条消息头和点云字段后自动退出；不发布任何
目标、轨迹、地图或 TF。只有其结果为 `"passed": true` 后，才可决定独立全局建图器
应直接接收传感器点云，还是需要由传感器位姿恢复观测原点。

## 03B 接受标准

集成验证必须同时满足：

| 检查项 | 要求 |
|---|---|
| 自主性 | 无人工航点、路线、目标坐标和区域划分 |
| 点云接口 | 已记录实际话题、`frame_id`、频率和消息类型 |
| 坐标变换 | 点云输入时 `world -> sensor` 可用，或采用有理论依据的替代融合方式 |
| FUEL 行为 | 仍由前沿自主产生视点和轨迹，能够完成或明确记录失败 |
| 独立地图 | 输出随时间增长，最终可导出并离线评价 |
| 结果隔离 | FUEL 规划图、独立全局图、场景真值三者文件和指标分别命名 |

如果传感器只提供世界坐标点而没有传感器原点，不能直接把该点云接入 OctoMap 做自由空间射线更新。那种情况需要改用带位姿的点云融合器或补充传感器坐标系话题，不能为了得到一张图而错误接线。

## 参考文献

[1] B. Zhou, Y. Zhang, X. Chen, and S. Shen, "FUEL: Fast UAV Exploration
Using Incremental Frontier Structure and Hierarchical Planning," *IEEE
Robotics and Automation Letters*, 2021. DOI: 10.1109/LRA.2021.3054415.

[2] F. Kong et al., "MARSIM: A Light-Weight Point-Realistic Simulator for
LiDAR-Based UAVs," *IEEE Robotics and Automation Letters*, vol. 8, no. 5,
pp. 2954-2961, 2023. DOI: 10.1109/LRA.2023.3264163.

[3] A. Hornung, K. M. Wurm, M. Bennewitz, C. Stachniss, and W. Burgard,
"OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees,"
*Autonomous Robots*, vol. 34, pp. 189-206, 2013.
DOI: 10.1007/s10514-012-9321-0.
