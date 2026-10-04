\# D3 证据



\## 反向验证：RECOVERED 后发新异常



\- 时间：2026-10-04

\- 操作：evt-reach-b-20261004013629 已 RECOVERED 后，

&#x20; 向 reach-b 发送新异常 waterLevel=9.5, flowLevel=2

\- 结果：

&#x20; - 旧事件保持 RECOVERED，未被改回

&#x20; - 创建新事件 evt-reach-b-20261004023000，state = OPEN

\- 符合契约第 6.2、6.3 节

\- 截图：reverse\_verify\_recovered\_locked.png

