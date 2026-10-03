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