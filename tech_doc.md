# TideWatch 技术文档（初稿）

> 面向多河道断面的河道水位与水质智能监测、预警与多端协同系统。
> 本文档描述 D1–D5、E1–E3 阶段的实现设计，与 `contract.md`、`README.md` 及 `Evidence/` 中的证据一一对应。所有机制描述均以仓库实际代码为准。

## 1. 项目与需求

### 1.1 项目目标

TideWatch 面向一条河道的三个监测断面 reach-a（上游）、reach-b（中游）、reach-c（下游），持续采集水位（waterLevel）、浊度（turbidity）与水流等级（flowLevel），并完成以下闭环：

- **判级**：按统一规则把每个断面的实时数据判为洪水预警 / 高水位警戒 / 水质浑浊 / 正常（contract 第 3 节）；
- **预警**：异常数据自动创建事件，按 OPEN → HANDLING → RECOVERED 状态机流转（contract 第 6 节）；
- **优先关注**：用环境分 + 感知分 + 持续分计算每个断面的优先分，自动标出当前最值得关注的断面（contract 第 7 节）；
- **多端协同**：Web 监测台、移动端现场巡查、3D 河道场景围绕同一条 MQTT 数据流工作，事件与干预动作跨端同步（contract 第 10 节）；
- **对照裁决**：固定规则与 IsolationForest 异常检测结果对照，加权组合裁决，规则正常而 ML 明显异常时提示人工复核（contract 第 8 节）。

### 1.2 使用场景

| 角色 | 场景 | 对应端 |
| --- | --- | --- |
| 值班人员 | 值班室大屏总览三断面实时状态、事件流转、规则/ML 对照 | web/index.html |
| 现场巡查员 | 手机上只看当前优先关注断面，一键执行干预动作 | mobile/index.html |
| 调度/展示 | 3D 河道上定位异常断面、观察水位柱与水流动画 | map3d/index.html |
| 复盘分析 | 历史 CSV 的统计与趋势报告 | python/analyze.py → report/report.html |
| 免手/取证 | 语音指令、结论朗读、现场拍照并生成感知记录 | Web 多模态交互区（E2） |

### 1.3 核心问题与设计约束

本项目要解决的核心问题不是"画一个监测大屏"，而是**多端围绕同一条数据流的正确性**：

1. 三个断面的数据不能串线，所有状态以 reachId 为唯一 key（contract 第 1 节）；
2. status 必须由规则计算，不能手填（contract 第 3 节）；
3. 事件状态转移必须走合法路径，重复、乱序、迟到消息不得破坏状态机（contract 6.2/6.3/6.5）；
4. 三端不能各自维护互不关联的状态，事件与干预必须跨端广播（contract 第 5 节、E3）；
5. ML 结果必须如实标注来源，simulated 数据不得伪造置信度（contract 4.3）。

## 2. 系统架构与数据链

### 2.1 整体架构

```
┌────────────────────┐        ┌──────────────────────┐        ┌──────────────────────────────┐
│  mqtt/simulator.py │ publish│  Mosquitto Broker    │subscribe│ 三端（浏览器，WS 8083）        │
│  模拟感知节点×3     │───────>│  localhost:1883      │───────>│  web/index.html   监测台      │
│  (reach-a/b/c)     │        │  localhost:8083 (WS) │        │  mobile/index.html 现场巡查  │
└─────────┬──────────┘        └──────────────────────┘        │  map3d/index.html 3D 场景    │
          │ append                                            └──────────────────────────────┘
          ▼
data/tidewatch_history.csv ──┬──> python/analyze.py ──> report/report.html + report/img/
                             └──> python/ml_detect.py ──> web/d5_compare.json ──> Web D5 对照区
```

- Broker 双监听：1883（MQTT）供模拟节点，8083（WebSocket）供浏览器三端，QoS 1，匿名访问（mqtt/mosquitto.conf）；
- 前端库全部本地化（mqtt.min.js、three.min.js r128、OrbitControls.js），不依赖 CDN 与外网——这是本项目早期诊断出 unpkg CDN 加载失败后的修复决策；
- Web 是事件状态的权威端：事件创建与状态变化由 Web 广播 `tidewatch/event/update`；干预动作两端都可发起，经 `tidewatch/intervention` 互相同步（E3）。

### 2.2 离线分析链（contract 9.1）

断面采集/历史记录 → CSV → Python → 时空统计/趋势 → report.html，实现如下：

| 环节 | 实现 |
| --- | --- |
| 历史记录 | simulator.py 每次发布的同时把同一份 payload 追加到 data/tidewatch_history.csv（表头只写一次）；也可由 MQTT 模拟节点手动准备 |
| 统计 | python/analyze.py 用 pandas 按断面统计：条数、水位均值/最大值、浊度均值/最大值、异常条数（status ≠ 正常） |
| 趋势 | matplotlib 画各断面水位/浊度趋势图，标注 8.5 / 7.0 警戒线，输出 report/img/*.png |
| 报告 | 汇总写入 report/report.html，报告由脚本生成，不靠手工修改 |

### 2.3 边缘实时链（contract 9.2）

```
水文采集节点 → MQTT/JSON → 共享实时状态 → Web监测台 + 移动端 + 地图/3D

simulator.py                     tidewatch/{reachId}/state
(3 断面 × 3 轮, 每 3 秒一条) ──────────────┬──> web/index.html    订阅 tidewatch/+/state
                                          ├──> mobile/index.html 订阅同一套 Topic
                                          └──> map3d/index.html  订阅同一套 Topic
```

三端消费同一条消息：同一份 JSON（reachId, waterLevel, turbidity, flowLevel, status, time），各自按分工渲染。事件链路为：Web 创建/流转事件 → 广播 `tidewatch/event/update` → 移动端与 3D 更新；任一端干预 → 广播 `tidewatch/intervention` → 对端更新。移动端不发 event/update，避免广播环路。

## 3. 核心数据与系统机制

### 3.1 数据结构（contract 第 2 节）

统一 JSON 六字段：`reachId, waterLevel, turbidity, flowLevel, status, time`。time 格式 `YYYY-MM-DD HH:mm:ss`；status 只能由判级规则计算；flowLevel 取值 0–3（缓流/平稳/湍急/湍流），本阶段来源为 simulated（contract 4.3）。

事件对象字段（contract 6.6）：`event_id, reachId, start_time, problem, priority_reason, action, verify_data, state, recover_time`。event_id 由 Web 生成（`evt-{reachId}-{时间戳}`）；problem 记录触发原因（水位异常/水质异常/水流异常，可多选）；verify_data 记录 HANDLING 期间收到的后续数据。

感知结果记录字段（contract 4.2）：`reachId, imageId, flowLevel, confidence, source, time`。拍照后生成；source=simulated 时 confidence 恒为 null，不伪造置信度。

### 3.2 Topic 结构与消息处理管线

Topic 三张（contract 第 5 节）：

| Topic | 方向 | 用途 |
| --- | --- | --- |
| `tidewatch/{reachId}/state` | 模拟节点 → 三端 | 断面实时状态 |
| `tidewatch/event/update` | Web → 移动端/3D | 事件创建与状态变化广播（9 字段完整载荷） |
| `tidewatch/intervention` | Web ↔ 移动端 | 干预动作 {event_id, reachId, action} |

Web 收到 `tidewatch/+/state` 消息后的处理管线（按顺序）：

1. **JSON 解析**：失败即拒绝（D4 故障演示的"发送错误 JSON"触发此层）；
2. **Topic 校验**：`/state` 后缀但断面不在 reach-a/b/c 内 → 拒绝（D4"发送错误 Topic"触发）；
3. **数据质量前置**（contract 8.4 的实现部分）：reachId/waterLevel/turbidity 字段缺失或类型错误、time 缺失/格式错误 → 拒绝并计数；
4. **去重**（contract 6.5）：优先 message_id，否则 reachId+time+载荷哈希；event_id 不参与去重；
5. **乱序/迟到**：time 不晚于该断面最新时间才生效，否则丢弃并计数（迟到消息进 lateMessages 供 F12 查看）；
6. **状态更新**：更新 state、连续异常 streak（正常清零）；
7. **事件状态机**：正常→非正常创建 OPEN；HANDLING 用新数据做恢复判定；
8. **渲染**：卡片、优先关注、事件列表、D5 对照表。

### 3.3 事件状态机（contract 6.2）

状态：OPEN（待处理）→ HANDLING（处理中）→ RECOVERED（已恢复）。

```
           正常数据判级为异常
  （无未关闭事件且之前为正常）        用户选择干预动作
  ───────────────────────> [OPEN] ────────────────> [HANDLING]
                               ^                        │
                               │                        │ 新数据满足恢复条件(6.4)
                               │ 数据恶化/干预未生效      ▼
                               └────────────────── [RECOVERED]（锁定）
```

- 允许的转移：新异常 → OPEN；用户干预 → HANDLING；后续新数据满足恢复条件 → RECOVERED；数据恶化/干预未生效 → 回退 OPEN 或保持。
- 禁止的转移（contract 6.3）：OPEN 直跳 RECOVERED；低置信度感知触发 HANDLING → RECOVERED；迟到/重复消息把已 RECOVERED 改回 HANDLING。
- 恢复判定（contract 6.4）按触发原因：水位异常 → waterLevel < 7.0；水质异常 → turbidity < 60；水流异常 → flowLevel ≤ 1；多原因需全部满足。恢复只能由新数据触发，不能由按钮触发。
- RECOVERED 后事件状态锁定，不再响应后续消息。
- 实现约束：每断面最多一个未关闭事件（openEventByReach 防重复创建）；HANDLING 期间每条新数据追加进 verify_data。

### 3.4 消息健壮性（contract 6.5）

- **去重**：双键方案——message_id 优先（`m:` 前缀），否则载荷哈希（reachId|time|waterLevel|turbidity|flowLevel，`h:` 前缀）；同一条消息只生效一次；
- **乱序**：每断面维护 latestTimeByReach，time ≤ 最新时间的消息不覆盖状态；
- **迟到**：早于当前状态时间戳的消息不回滚已 RECOVERED 事件，最多作历史补充；
- **事件消息同样去重**：event/update 与 intervention 按 message_id 或原始载荷哈希去重，重复广播只生效一次；
- **状态单调守卫**：STATE_ORDER = {OPEN:1, HANDLING:2, RECOVERED:3}，任何消息不得把状态改回更小的值——这是 6.3"非法转移"在跨端场景下的实现方式。

### 3.5 感知结果组织（contract 4.2）

E2 的拍照流程生成感知记录并存入页面内存列表：reachId 取当前查看断面（未指定则取优先关注断面），imageId 按 `img-{reachId}-{时间戳}` 生成，flowLevel 取该断面当前值，confidence=null，source="simulated"，time 为拍照时刻。照片以 dataURL 存内存并显示缩略图，可手动下载为 PNG。感知记录与照片关联当前活跃事件 event_id（如有）。

### 3.6 Web-移动端同步（E3）

同步由两类消息承载：

- 事件广播：Web 在事件创建、干预、恢复时发布 `tidewatch/event/update`（完整 9 字段 + source），移动端与 3D 订阅后按 STATE_ORDER 守卫更新；
- 干预广播：两端发布 `tidewatch/intervention` {event_id, reachId, action}，对端收到后把事件置为 HANDLING 并记录 action；HANDLING 且 action 相同视为重复（幂等），RECOVERED 直接拒绝。

去重与守卫保证：任意一方重复点击、消息重复投递、迟到到达，都不会造成两端状态分叉。

## 4. D1–D5 关键实现

### 4.1 D1 多断面稳定运行

simulator.py 按"每轮 3 个断面各发 1 条，共 3 轮，间隔 3 秒"的节奏发布；status 由 make_status() 按 contract 第 3 节规则计算（≥8.5 洪水预警；≥7.0 高水位警戒；≥60 水质浑浊；否则正常），载荷不含任何手填状态。演示数据三断面不串线：reach-a 水位型（4.5/5.0/7.6）、reach-b 洪水型（9.0/7.8/6.5）、reach-c 浊度型（75/68/55）。三端订阅同一 Topic，一条消息同时驱动三端更新（Evidence/D1/one_message_three_ends.png、three_ends_online.png）。

### 4.2 D2 持续风险与优先关注

优先分 = 环境分 + 感知分 + 持续分（contract 7.1）：环境分按状态 3/2/1/0；感知分直接取 flowLevel（0–3）；持续分按连续异常次数（≥3 次 → 2 分，1–2 次 → 1 分，正常清零）。实现要点：streak 计数挂在每条消息处理之后；正常消息清零、异常消息 +1；每次渲染重算所有断面总分，最高分断面加 `priority` 样式并在顶部横幅显示。优先对象随数据自然切换，不写死任何断面——Evidence/D2 的三组验证分别展示了 reach-b（洪水+flow2）、reach-a（高水位+flow3）、reach-c（水质浑浊+持续）各自成为优先关注的场景（group1.png、group2.png）。

### 4.3 D3 事件状态机与消息健壮性

分四步落地：D3-1 正常→非正常且无未关闭事件时创建 OPEN（problem 按水位/水质/水流多选记录，priority_reason 引用优先分）；D3-2 每个 OPEN 事件带"开始干预"按钮，弹窗三选一（开闸泄洪/开启泵站/投加净水剂），点击后 state=HANDLING、action 记录动作，无动作不变状态；D3-3 恢复判定由后续新数据触发（6.4），满足则 RECOVERED 并记录 recover_time，未满足保持 HANDLING 并追加 verify_data；D3-4 实现 3.4 节的去重/乱序/迟到机制，并在测试面板提供"发送重复数据""发送旧数据""发送带 message_id 的消息"按钮，页面顶部显示已处理/重复丢弃/乱序迟到/拒绝计数。反向验证见 Evidence/D3/reverse_verify_recovered_locked.png。

### 4.4 D4 故障演示与修复

按 contract 第 11 节计划制造两类故障：测试面板"发送错误 Topic"向 `tidewatch/wrong-topic/state` 发消息（载荷带 2000 年时间戳，即使无 Topic 校验的端也会被乱序守卫丢弃，保证不破坏系统状态）；"发送错误 JSON"发布 `{reachId: reach-a, waterLevel: }`。Web 端解析失败/校验失败后拒绝计数 +1 并显示最近拒绝原因，三端与事件状态不受影响。修复验证：点"发送带 message_id 的消息"或跑 simulator，三端恢复正常更新（Evidence/D4/before_fault.png、bad_json.png、after_fix.png）。

### 4.5 D5 规则/ML 对照

python/ml_detect.py 用 pandas 读历史 CSV（自动修复手写段与追加段的行粘连），每个断面独立训练 IsolationForest（特征 waterLevel/turbidity/flowLevel，contamination=0.1，random_state=42），避免跨断面形态互相污染。ML 标签按固定映射从 decision_function 分数与 predict 投票得到：明显异常（投票判异常且分数<0）/ 偏离历史（分数<0）/ 略偏（0≤分数<0.1）/ 接近历史（≥0.1）。每条输出 status_rule（规则重算并与 CSV 交叉核对）、status_ml、is_consistent，写入 web/d5_compare.json。Web 端 fetch 该文件后按 (reachId, waterLevel, turbidity, flowLevel) 四元组为每条实时消息查对照：表格展示规则判断/ML 判断/一致性，不一致行红底；组合裁决按 contract 8.3（规则 0.7 + ML 0.3，规则正常 + ML 明显异常 → 需人工复核）。另有 2 个标注构造样本不参与训练：reach-a (6.8,45,2) 规则正常/ML 明显异常（8.3 需人工复核场景），reach-b (9.2,20,2) 规则洪水预警/ML 略偏（模型把反复出现的历史洪水学成常态）。自然数据同样出现不一致：reach-b/c 的异常形态因反复出现被 ML 判接近历史，reach-a 的 4.7/22 与 5.0/25 被 ML 判明显异常而规则判正常——这正是对照的价值（Evidence/D5/d5_table.png）。

## 5. E1–E3 关键实现

### 5.1 E1 Three.js 3D 河道场景

map3d/index.html 用本地 three.min.js（r128）+ OrbitControls 构建三河段场景：每个断面一个 Group（河床/水面/水位柱/泡沫粒子/标签/事件图标/优先光环）。水位柱高度随 waterLevel 线性映射；水面与柱体颜色随 status（正常绿/高水位橙/洪水红/浑浊紫）；泡沫流动速度随 flowLevel（0.25 + flow×0.55）；事件图标按状态闪烁（OPEN 红快闪、HANDLING 橙慢闪、RECOVERED 绿常亮），事件状态来自 event/update 订阅并在无事件流时用本地 OPEN 推断兜底；优先关注断面带金色旋转脉动光环。点击河段用 Raycaster 命中水面/柱体/河床，BoxHelper 高亮描边并显示六字段详情面板。动画循环用独立累加器修复了 getElapsedTime/getDelta 同帧调用导致的冻结问题（Evidence/E1/3d_overview.png、click_detail.png、live_update.png）。

### 5.2 E2 Camera / ASR / TTS 多模态交互

Web 页"多模态交互"区三项能力：

- **ASR**：Web Speech API（zh-CN）识别两条指令——"查看 reach-a/b/c"切换当前查看断面（卡片蓝色描边并滚动定位），"朗读结论"触发 TTS；识别结果实时显示，未识别指令给出提示；浏览器不支持时按钮给出明确提示；
- **TTS**：SpeechSynthesis 朗读当前查看断面（未指定时取优先关注断面）的真实 MQTT 状态，句式"reach-a，水位 7.6，浊度 20，水流平稳，状态高水位警戒"，内容全部来自 state 中的实时数据与 flowLevel 映射表，无写死文本；
- **Camera**：getUserMedia 打开摄像头（优先后置）→ 弹层预览 → 拍照 → canvas 转 dataURL 存内存、显示缩略图、关联 reachId/时间/当前事件 event_id，并按 3.5 节生成感知记录；"保存图片"下载 PNG。

（Evidence/E2/asr_command.png、tts_speaking.png、camera_photo.png、perception_record.png）

### 5.3 E3 事件跨端广播与移动端干预同步

见 3.6 节机制。实现要点：Web 为 event/update 权威端（移动端永不发 event/update，杜绝广播环路）；干预消息必须携带 reachId 与 action；两端共用 STATE_ORDER 单调守卫 + 事件消息去重 + RECOVERED 拒绝 + 同 action 幂等，保证任意操作顺序下两端状态最终一致（Evidence/E3/sync_both.png、mobile_to_web.png、recover_sync.png）。

## 6. 测试、故障与验证

### 6.1 D1–D5 测试

- **D1**：三端同时打开订阅同一 Topic，模拟器 3 轮期间三端同步刷新、数据不串线（Evidence/D1/three_ends_online.png、one_message_three_ends.png）；
- **D2**：构造三组数据让 reach-b / reach-a / reach-c 分别成为优先关注，验证优先分计算与高亮切换（Evidence/D2/group1.png、group2.png）；
- **D3**：正向验证 OPEN→HANDLING→RECOVERED 全流程；反向验证——RECOVERED 后发新异常不回退、重复消息只生效一次、旧消息被丢弃（Evidence/D3/duplicate_dropped.png、late_message.png、message_id_dedup.png、reverse_verify_recovered_locked.png）；
- **D4**：故障注入 → 观察拒绝统计 → 发正确消息 → 三端恢复（Evidence/D4/before_fault.png、bad_json.png、after_fix.png）；
- **D5**：对照表逐条核对规则与 ML 输出、不一致行高亮、构造案例人工复核提示；权重可经 ml_detect.py 或 JS 常量两条路径修改后验证裁决变化（Evidence/D5/d5_table.png）。

### 6.2 D4 故障修复流程

按 contract 第 11 节"观察现象 → 定位原因 → 修复 → 重新运行 → 验证恢复"执行：错误 Topic 消息在 Web 端被 Topic 校验拒绝，错误 JSON 在解析层被拒绝，两者都计入"拒绝: N"统计并展示最近拒绝原因；修复方式即改回正确 Topic/载荷后重新发布，三端恢复更新。设计上保证故障消息不破坏状态：错误 Topic 载荷带 2000 年时间戳，即使落在无校验的端也会被乱序守卫丢弃。

### 6.3 D5 规则/ML 对照测试

训练与预测全自动：`python python/ml_detect.py` 一键从 CSV 生成 web/d5_compare.json；Web 端实时消息按值查对照。测试覆盖三类结果：一致（规则与 ML 同判）、规则异常而 ML 正常（历史异常被学成常态）、规则正常而 ML 明显异常（触发 8.3 需人工复核）。构造样本保证"值得分析"案例在数据分布变化后依然存在，并逐条标注说明。

## 7. 自主设计与开放拓展

### 7.1 自主设计点

1. **前端库全面本地化**：诊断出 unpkg CDN 在目标网络不可达导致"未连接"后，把 mqtt.js / three.js / OrbitControls 全部下载到仓库，并在 mqtt.connect() 前加 `typeof mqtt === "undefined"` 守卫（红色提示 + throw），彻底摆脱外网依赖；
2. **消息健壮性测试面板**：把 D3-4 的去重/乱序/迟到做成可点击按钮（重复/旧数据/message_id/错误 Topic/错误 JSON），并新增"手动发布"表单（reachId + 三数值输入，status 与 time 自动生成），使状态机全流程可在页面上徒手复现；
3. **故障安全设计**：D4 故障载荷带 2000 年时间戳，保证即使某端缺少 Topic 校验也不会被污染；
4. **CSV 自动修复**：ml_detect.py / analyze.py 读取时自动修复手写历史末尾无换行造成的行粘连，不改动原文件；
5. **D5 双路径权重验证**：权重既由 ml_detect.py 写入 JSON 展示，也以 JS 常量参与裁决计算，两条修改路径都可验证权重对裁决的影响。

### 7.2 开放拓展（contract 第 12 节，本阶段未做）

真实视觉感知（source=model，flowLevel 带置信度）、FastAPI/SQLite 持久化后端（事件与照片落库、跨刷新恢复）、PWA 移动端、云端部署、更多故障演练类型（contract 11 未勾选项：停止 Broker、改错字段名、断面长时间不发数据、感知服务失败）。

## 8. 已知限制

- flowLevel 本阶段来源为 simulated（contract 4.3），无真实视觉模型，感知记录 confidence 恒为 null，不伪造置信度；
- 固定规则阈值仅用于编程练习，不代表真实水文防汛标准（contract 13）；
- IsolationForest 训练样本量小（每断面数十条），标签阈值是固定定义；历史累积后重跑 ml_detect.py 可更新对照，但误报/漏报风险存在；
- 事件、去重集合、照片、感知记录均为页面内存态，刷新即重置，无后端持久化；
- D5 对照区依赖 fetch，页面必须经 http 访问（file:// 直开会被 Chrome 拦截）；ASR/TTS 仅 Chrome/Edge 支持；
- 移动端按巡查分工只显示优先关注断面，不显示全部断面列表；
- 系统面向本机/局域网演示，未做云端部署（contract 13）。
