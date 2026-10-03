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

本阶段不做；如后续实现，同一断面 24 小时内重复异常合并为同一事件并升级严重度。git