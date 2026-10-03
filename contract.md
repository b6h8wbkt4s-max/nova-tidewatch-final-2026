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