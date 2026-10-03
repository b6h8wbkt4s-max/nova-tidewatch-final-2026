# TideWatch 统一契约 contract.md

## 1. 统一监测断面

| reachId | 位置 | 说明 |
|---|---|---|
| reach-a | 上游 | |
| reach-b | 中游 | |
| reach-c | 下游 | |

**约定：**
- 三个断面历史与状态不能串线。
- 所有状态以 `reachId` 为唯一 key，不用数组下标。
## 2. 统一 JSON 字段

| 字段 | 类型 | 含义 | 来源 |
|---|---|---|---|
| reachId | string | 断面标识 | 采集节点 |
| waterLevel | number | 水位 | 水文传感/模拟 |
| turbidity | number | 浊度 | 水质传感/模拟 |
| flowLevel | int 0-3 | 水流等级（感知维度） | 见第 4 节 |
| status | string | 环境状态（环境维度） | 由规则计算 |
| time | string | 感知/采集时间 | 采集节点 |

**time 格式：** `YYYY-MM-DD HH:mm:ss`

**status 必须由 waterLevel/turbidity 按第 3 节规则计算，不能手填。**
## 3. 统一判级规则（按顺序判断）

① waterLevel >= 8.5            → 洪水预警
② 否则 waterLevel >= 7.0       → 高水位警戒
③ 否则 turbidity >= 60         → 水质浑浊（此时 waterLevel < 7.0）
④ 其余                          → 正常

**说明：** 判断顺序体现水位维度优先。此阈值仅用于编程练习。
### 回归测试数据

| waterLevel | turbidity | 期望 status |
|---|---|---|
| 4.5 | 20 | 正常 |
| 7.6 | 20 | 高水位警戒 |
| 9.0 | 20 | 洪水预警 |
| 4.5 | 75 | 水质浑浊 |
### 三断面演示数据

| reachId | waterLevel | turbidity | flowLevel | 期望 status |
|---|---|---|---|---|
| reach-a | 4.5 | 20 | 0 | 正常 |
| reach-b | 9.0 | 20 | 2 | 洪水预警 |
| reach-c | 4.5 | 75 | 1 | 水质浑浊 |
## 4. flowLevel 水流等级与感知结果记录

### 4.1 flowLevel 含义

| flowLevel | 含义 |
|---|---|
| 0 | 缓流 |
| 1 | 平稳 |
| 2 | 湍急 |
| 3 | 湍流 |

### 4.2 感知结果记录字段

| 字段 | 含义 |
|---|---|
| reachId | 所属断面 |
| imageId | 关联图像标识（文件名/哈希/自编号），非图像来源可空 |
| flowLevel | 水流等级 0-3 |
| confidence | 自动感知置信度 0-1；simulated/rule/review 填 null |
| source | simulated / rule / model / template / review |
| time | 感知时间 |

### 4.3 本作品采用的 flowLevel 来源

- [x] simulated（模拟/回放）
- [ ] rule（规则映射）
- [ ] model（模型推理）
- [ ] template（模板比对）
- [ ] review（人工复核）

**说明：** 共同完成线阶段采用 simulated，由 MQTT 模拟节点显式指定 flowLevel，便于先跑通环境事件—多端同步主链。开放增强阶段可另行接入 model/template 自动感知。

**置信度阈值：** 不适用（simulated 不伪造模型置信度）

**低置信度处理：** 本阶段不涉及；若后续接入 model/template，低于 0.6 标“需人工复核”，保留原始记录并另存 source=review 复核记录。

### 4.4 与统一 JSON 的关系

flowLevel 一并写入统一 JSON 状态流，随每条 MQTT 状态消息发布。感知结果记录另行保存到 Evidence/E2/，以 reachId + time 关联回状态流。
## 5. MQTT / Topic 结构

| 用途 | Topic | 说明 |
|---|---|---|
| 断面状态 | `tidewatch/{reachId}/state` | 每个断面一条 |
| 事件更新 | `tidewatch/event/update` | 事件状态变化 |
| 干预动作 | `tidewatch/intervention` | 用户干预 |

**Broker 地址：** localhost
**MQTT 端口：** 1883
**WebSocket 端口：** 8083
**QoS：** 1

**订阅方式：** Web / 移动端 / 地图3D 订阅 `tidewatch/+/state`，一次订阅三个断面。

**消息去重依据：** 优先使用 `message_id`；若无，则用 `reachId + time + waterLevel + turbidity + flowLevel` 的哈希。event_id 只用于标识事件，不用于消息去重。
## 6. 事件状态机

### 6.1 状态定义

| 状态 | 含义 |
|---|---|
| OPEN | 待处理 |
| HANDLING | 处理中 |
| RECOVERED | 已恢复 |

### 6.2 状态转移表

| 当前状态 | 允许转移到 | 触发条件 | 说明 |
|---|---|---|---|
| （无） | OPEN | 出现新异常 | 新事件创建 |
| OPEN | HANDLING | 用户执行干预动作 | 必须有干预动作 |
| HANDLING | RECOVERED | 后续新数据满足恢复条件 | 必须由数据触发 |
| HANDLING | OPEN | 数据进一步恶化/干预未生效 | 允许回退 |
| OPEN/HANDLING | （保持） | 仅点击按钮、无新数据 | 不得改变状态 |

### 6.3 非法转移（出现即算未达标）

- OPEN → RECOVERED 直接跳过
- 低置信度感知触发 HANDLING → RECOVERED
- 迟到/重复消息把已 RECOVERED 改回 HANDLING

### 6.4 恢复判定规则

若事件由水位异常触发，恢复需 waterLevel < 7.0；
若事件由水质异常触发，恢复需 turbidity < 60；
若事件同时由水流异常触发，恢复还需 flowLevel ≤ 1。

以上相关条件都满足，或经人工复核确认，才进入 RECOVERED。

### 6.5 消息健壮性

| 情况 | 处理方式 |
|---|---|
| 重复 | 用 message_id 或哈希去重，同一条只生效一次 |
| 乱序 | 按 time 排序后再判断状态 |
| 迟到 | 早于当前状态时间戳的消息不回滚已 RECOVERED 事件，最多作历史补充 |

### 6.6 事件关联字段

| 字段 | 含义 |
|---|---|
| event_id | 事件标识 |
| reachId | 所属断面 |
| start_time | 开始时间 |
| problem | 问题/异常（水位/水质/水流） |
| priority_reason | 为什么被优先关注 |
| action | 用户采取的动作 |
| verify_data | 后续验证数据 |
| state | 当前事件状态 |
| recover_time | 恢复时间/最终结果 |

### 6.7 事件合并与升级（可选）

本阶段不做；如后续实现，同一断面 24 小时内重复异常合并为同一事件并升级严重度。

## 7. 优先关注规则

**设计原则：** 可解释、可重复、随数据变化，不能把 reach-c 写死。

### 7.1 评分设计

优先分 = 环境分 + 感知分 + 持续分

| 维度 | 取值 | 分值 |
|---|---|---|
| 环境分 | 洪水预警 | 3 |
| | 高水位警戒 | 2 |
| | 水质浑浊 | 1 |
| | 正常 | 0 |
| 感知分 | flowLevel 3 | 3 |
| | flowLevel 2 | 2 |
| | flowLevel 1 | 1 |
| | flowLevel 0 | 0 |
| 持续分 | 连续异常 ≥3 次 | 2 |
| | 连续异常 1-2 次 | 1 |
| | 正常 | 0 |

**当前优先关注 = 优先分最高的断面。**

### 7.2 低置信度处理

本阶段 flowLevel 来源为 simulated，不涉及置信度阈值。
若后续接入 model/template，低于 0.6 的结果标“需人工复核”，不参与优先分计算，直到人工复核确认。

### 7.3 变化验证

| 组 | reach-a | reach-b | reach-c | 期望优先 |
|---|---|---|---|---|
| 1 | 正常 | 水质浑浊 | 洪水预警+flowLevel2+持续3次 | reach-c |
| 2 | 洪水预警+flowLevel3+持续3次 | 正常 | 正常 | reach-a |
| 3 | 正常 | 高水位警戒+flowLevel2+持续2次 | 水质浑浊+flowLevel1+1次 | reach-b |

## 8. 规则 / ML 组合裁决策略

### 8.1 策略类型

- [ ] 规则优先
- [ ] ML 优先
- [x] 加权打分
- [ ] 交集从严
- [x] 分场景切换

### 8.2 选择理由

本作品 ML 使用轻量 IsolationForest，历史数据有限，可信度低于固定规则；
固定规则来自任务书统一判级规则，可信度高。
因此默认采用加权打分，规则权重高于 ML；
当规则与 ML 明显不一致时，切换为“需人工复核”，不直接升级为预警。

### 8.3 裁决参数

规则权重 = 0.7
ML 权重 = 0.3

最终风险分 = 0.7 × 规则分 + 0.3 × ML 分

规则分：
  洪水预警 = 3
  高水位警戒 = 2
  水质浑浊 = 1
  正常 = 0

ML 分：
  明显异常 = 3
  偏离历史 = 2
  略偏 = 1
  接近历史 = 0

最终建议：
  >= 2.5 → 需重点关注
  1.5 - 2.5 → 需关注
  < 1.5 → 正常

分场景切换：
  若规则判断“正常”但 ML 判断“明显异常”，
  最终建议标为“需人工复核”，不直接升级为预警。

现场可临时改权重（如 0.7 → 0.5），验证结果跟着变。

### 8.4 数据质量前置检查

| 问题 | 处理方式 |
|---|---|
| 缺失 | waterLevel/turbidity 缺字段或缺值时，不得让规则算出错误状态，直接拒绝该条消息 |
| 离群 | 明显超出量程的值（如 waterLevel 1000）应标记或拦截 |
| 时钟 | time 缺失、格式错误或时间倒流时，拒绝该条消息或标记异常 |

## 9. 数据链定义

### 9.1 离线分析链

断面采集/历史记录 → CSV → Python → 时空统计/趋势 → report.html

| 环节 | 实现 |
|---|---|
| 断面采集/历史记录 | MQTT 模拟节点写入 CSV，或手动准备 |
| CSV | data/tidewatch_history.csv |
| Python | python/analyze.py，用 pandas 统计 |
| 时空统计/趋势 | 按断面统计均值、最大值、异常次数；按时间画趋势图 |
| report.html | report/report.html，由 Python 生成 |

**要求：**
- 数据来自系统真实运行或明确标注的模拟运行
- 换一份新 CSV 后，分析结果能重新生成
- 报告不能靠手工修改结果完成

### 9.2 边缘实时链

水文采集节点 → MQTT/JSON → 共享实时状态 → Web监测台 + 移动端 + 地图/3D

| 环节 | 实现 |
|---|---|
| 水文采集节点 | mqtt/simulator.py，3 个断面定时发布 |
| MQTT/JSON | Topic tidewatch/{reachId}/state，JSON 六字段 |
| 共享实时状态 | Broker 上的 retained 消息或内存状态 |
| Web 监测台 | web/index.html，订阅 tidewatch/+/state |
| 移动端 | mobile/，订阅同一套 Topic |
| 地图/3D | map3d/，订阅同一套 Topic |

**要求：**
- 至少 3 个断面节点
- 三个断面数据不能串线
- 新消息到达后，三端围绕同一条实时状态更新
- 三者共享同一套实时数据源

## 10. 多端分工

| 入口 | 承担任务 |
|---|---|
| Web 监测台 | 多断面实时总览、重点断面、热力分布、趋势、事件状态 |
| 移动端 | 现场快速查看当前重点、最新环境与感知结论、必要处置操作 |
| 地图/3D | 断面与空间对象对应，热力与色彩表达风险、状态和处置过程 |
| TTS | 朗读当前真实断面状态或预警事件 |
| Camera/感知 | 记录现场图像，给出水情强度感知结论 |
| report.html | 历史分析、事件时间线、今日摘要与复盘 |

**分工理由：**
Web 监测台信息密度高，适合值班室大屏总览；
移动端面向现场巡查，只保留当前重点、最新感知结论和必要干预操作，避免信息过载；
地图/3D 用空间表达帮助快速定位异常断面和处置过程；
TTS 用于免手操作的现场场景；
Camera/感知用于记录现场证据并给出水情强度结论；
report.html 用于事后复盘和历史分析。