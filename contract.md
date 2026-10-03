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