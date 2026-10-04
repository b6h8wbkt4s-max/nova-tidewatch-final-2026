\# E3 证据



\## 数据源



\- Web 和移动端订阅同一套 MQTT Topic：tidewatch/+/state

\- Broker：localhost:8083 (WebSocket)



\## 跨端同步验证



\### 1. 同步显示

\- 截图：sync\_both.png

\- Web 和移动端同一 reachId 的 waterLevel/turbidity/flowLevel/status/time 一致



\### 2. 移动端干预 → Web 同步

\- 移动端点"开闸泄洪"，事件变 HANDLING

\- Web 端同步显示 HANDLING

\- 截图：mobile\_to\_web.png



\### 3. 恢复同步

\- Web 端发恢复数据，事件变 RECOVERED

\- 移动端同步显示 RECOVERED

\- 截图：recover\_sync.png

