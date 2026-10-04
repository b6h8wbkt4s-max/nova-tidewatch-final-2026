\# E2 证据



\## ASR

\- 使用浏览器 Web Speech API

\- 支持指令：

&#x20; - "查看 reach-a" / "查看 reach-b" / "查看 reach-c"：切换当前断面

&#x20; - "朗读结论"：触发 TTS

\- 截图：asr\_command.png



\## TTS

\- 使用浏览器 SpeechSynthesis

\- 朗读内容来自当前真实断面状态（waterLevel、turbidity、flowLevel、status）

\- 截图：tts\_speaking.png



\## Camera

\- 使用 getUserMedia

\- 拍照后生成缩略图，关联 reachId、时间、事件

\- 至少 2 张不同角度/光照

\- 截图：camera\_photo.png



\## 感知结果记录

\- 字段：reachId、imageId、flowLevel、confidence=null、source=simulated、time

\- 截图：perception\_record.png

