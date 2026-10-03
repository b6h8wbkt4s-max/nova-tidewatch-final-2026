# TideWatch 项目约定

面向多河道断面的河道水位与水质智能监测、预警与多端协同系统。
详细契约见 `contract.md`，本文件只列 Claude 每次必须遵守的事实。

## 项目结构

- web/：Web 监测台
- mobile/：移动端
- map3d/：地图/3D
- python/：离线分析链
- perception/：Camera/感知
- mqtt/：MQTT 节点脚本
- data/：CSV、示例数据
- report/：report.html
- Evidence/：证据目录

## 统一监测断面

- reach-a（上游）
- reach-b（中游）
- reach-c（下游）

所有状态以 `reachId` 为唯一 key，不用数组下标。

## 统一 JSON 字段

reachId, waterLevel, turbidity, flowLevel, status, time

- time 格式：`YYYY-MM-DD HH:mm:ss`
- status 必须由 waterLevel/turbidity 按判级规则计算，不能手填

## 统一判级规则（按顺序判断）

1. waterLevel >= 8.5  → 洪水预警
2. 否则 waterLevel >= 7.0 → 高水位警戒
3. 否则 turbidity >= 60 → 水质浑浊
4. 其余 → 正常

## flowLevel

- 取值 0–3：0 缓流、1 平稳、2 湍急、3 湍流
- 本阶段 source = simulated
- 必须如实标 source，不得伪造模型置信度

## MQTT / Topic

- 断面状态：`tidewatch/{reachId}/state`
- 事件更新：`tidewatch/event/update`
- 干预动作：`tidewatch/intervention`
- Broker：localhost
- MQTT 端口：1883
- WebSocket 端口：8083
- QoS：1
- 三端订阅 `tidewatch/+/state`
- 去重：优先 message_id；否则 reachId + time + 载荷哈希
- event_id 不用于消息去重

## 事件状态机

状态：OPEN → HANDLING → RECOVERED

允许：
- 新异常 → OPEN
- 用户干预 → HANDLING
- 后续新数据满足恢复条件 → RECOVERED
- 数据恶化/干预未生效 → 回退 OPEN 或保持

禁止：
- OPEN 直跳 RECOVERED
- 低置信度感知触发 HANDLING → RECOVERED
- 迟到/重复消息把已 RECOVERED 改回 HANDLING

必须处理：
- 重复：去重，同一条只生效一次
- 乱序：按 time 排序后再判断
- 迟到：早于当前状态时间戳的消息不回滚已 RECOVERED 事件

## 优先关注规则

优先分 = 环境分 + 感知分 + 持续分

- 环境分：洪水预警 3、高水位警戒 2、水质浑浊 1、正常 0
- 感知分：flowLevel 3/2/1/0 对应 3/2/1/0
- 持续分：连续异常 ≥3 次 2、1–2 次 1、正常 0

取优先分最高的断面为“当前优先关注”。

禁止把 reach-c 写死为重点断面。

## 规则 / ML 裁决

- 默认加权打分：规则权重 0.7，ML 权重 0.3
- 规则判断“正常”但 ML 判断“明显异常”时，标“需人工复核”
- 现场可临时改权重验证结果变化

## 数据质量前置检查

- 缺失：waterLevel/turbidity 缺字段或缺值时拒绝该条消息
- 离群：明显超出量程的值（如 waterLevel 1000）标记或拦截
- 时钟：time 缺失、格式错误或时间倒流时拒绝或标记

## 禁止事项

- 不要把 reach-c 写死为重点断面
- 不要让 status 手填，必须由规则计算
- 不要让点击按钮直接改事件状态为 RECOVERED
- 不要让低置信度感知直接驱动处置或恢复
- 不要让三端各自维护互不关联的状态
- 不要手工修改 ML 输出或反复调参凑答案
- 不要用 event_id 作为消息去重依据

## 常用命令

- 启动 Broker：`mosquitto -c mosquitto.conf -v`
- 启动 MQTT 模拟节点：`python mqtt/simulator.py`
- 生成报告：`python python/analyze.py`
- 启动 Web：用浏览器打开 `web/index.html`，或本地静态服务器

## 参考

完整契约见 `contract.md`。