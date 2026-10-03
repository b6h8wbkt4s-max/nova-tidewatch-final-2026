---
name: mqtt-test
description: 发布一条 MQTT 测试消息，验证 Web 监测台、移动端、地图/3D 是否同步更新。
  当用户需要验证三端同步、测试新消息、检查数据链，或现场核验前做快速回归时使用。
---

## 目标

验证发布一条新的断面状态消息后，Web、移动端、地图/3D 都能识别这是同一个断面的新状态，并保持核心数据一致。

## 前置条件

- MQTT Broker 已启动
- Web 监测台、移动端、地图/3D 已打开并订阅
- 模拟节点或手动发布工具可用

## 步骤

1. 确认 Broker 正在运行：
   - 默认地址 localhost，MQTT 端口 1883，WebSocket 端口 8083
   - 如果 Broker 没启动，先启动，再继续

2. 构造一条 JSON 消息，字段必须齐全：
   ```json
   {
     "reachId": "reach-b",
     "waterLevel": 9.0,
     "turbidity": 20,
     "flowLevel": 2,
     "status": "洪水预警",
     "time": "2026-10-03 20:30:00"
   }

   ---
name: event-lifecycle
description: 走一遍 TideWatch 事件生命周期：发现异常 → 优先关注 → 用户干预 → 后续新数据验证 → 恢复/未恢复 → 事件记录。
  当用户需要演示 D3、验证事件状态机、测试恢复条件，或现场核验事件闭环时使用。
---

## 目标

验证一次异常能够作为持续事件，从 OPEN 走到 HANDLING，再由后续新数据触发 RECOVERED 或保持 HANDLING，且多端事件状态一致。

## 前置条件

- MQTT Broker 已启动
- Web 监测台、移动端、地图/3D 已打开
- 事件状态机已实现，且遵守契约第 6 节
- 消息去重、乱序、迟到处理已实现

## 步骤

1. 制造一次异常：
   - 发布 reach-c 状态：waterLevel >= 8.5，flowLevel = 2
   - 确认系统创建新事件，状态为 OPEN
   - 确认当前优先关注为 reach-c，且理由可解释

2. 用户执行干预：
   - 在 Web 或移动端点击“开始干预”按钮
   - 确认事件状态变为 HANDLING
   - 确认三端事件状态一致
   - 注意：仅点击按钮不能直接变 RECOVERED

3. 发送第一组后续新数据：
   - 发布 reach-c 新状态：waterLevel 从 9.0 降到 7.5，flowLevel 仍为 2
   - 按恢复判定规则，waterLevel 仍 >= 7.0，不满足恢复
   - 确认事件保持 HANDLING
   - 确认事件记录里新增了这条验证数据

4. 发送第二组后续新数据：
   - 发布 reach-c 新状态：waterLevel 降到 6.5，flowLevel 降到 1
   - 按恢复判定规则，waterLevel < 7.0 且 flowLevel <= 1，满足恢复
   - 确认事件状态变为 RECOVERED
   - 确认恢复时间被记录
   - 确认三端同步显示 RECOVERED

5. 检查事件记录字段：
   - event_id、reachId、start_time、problem、priority_reason、action、verify_data、state、recover_time
   - 所有字段应齐全

6. 如果事件未按预期变化，按以下顺序排查：
   - 恢复判定规则是否按契约第 6.4 节实现
   - 事件状态是否由数据触发，而不是按钮触发
   - 是否有低置信度感知结果被错误用于恢复
   - 三端是否共享同一套事件状态
   - 是否有重复/迟到消息干扰状态

## 消息健壮性测试

至少留一组证据：

1. 重复：同一条消息发两次，事件状态只变一次
2. 乱序：按 time 排序后再判断，旧消息不覆盖新状态
3. 迟到：早于当前状态时间戳的消息，不回滚已 RECOVERED 事件

## 非法转移检查

以下情况出现即算未达标：

- OPEN 直接跳 RECOVERED
- 低置信度感知触发 HANDLING → RECOVERED
- 迟到/重复消息把已 RECOVERED 改回 HANDLING

## 验证标准

- 完整走完：异常 → OPEN → 干预 → HANDLING → 后续数据 → RECOVERED
- 至少 2 组后续新数据
- 三端事件状态一致
- 事件记录字段齐全
- 重复/乱序/迟到至少留一组证据

## 证据

截图、短视频、JSON、日志放入 `Evidence/D3/`。