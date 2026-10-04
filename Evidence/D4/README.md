\# D4 故障与修复证据



\## 故障 1：写错 Topic



\- 操作：点击“发送错误 Topic”按钮，向 tidewatch/wrong-topic/state 发消息

\- 现象：三端不更新，顶部“拒绝”+1，“最近拒绝”显示：

&#x20; Topic 错误: tidewatch/wrong-topic/state

\- 定位：Web 端订阅 tidewatch/+/state，wrong-topic 不在订阅范围内

\- 修复：发正确 Topic

\- 截图：wrong\_topic.png



\## 故障 2：错误 JSON



\- 操作：点击“发送错误 JSON”按钮，发非法 JSON

\- 现象：拒绝 +1，Console 报 JSON 解析错误

\- 定位：消息体缺字段，不是合法 JSON

\- 修复：发合法 JSON

\- 截图：bad\_json.png



\## 修复后验证



\- 点“发送带 message\_id 的消息” → 三端正常更新

\- 截图：after\_fix.png

