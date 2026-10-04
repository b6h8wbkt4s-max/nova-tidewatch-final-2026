# TideWatch

面向多河道断面的河道水位与水质智能监测、预警与多端协同系统。

## 1. 项目简介

TideWatch 对 reach-a（上游）/ reach-b（中游）/ reach-c（下游）三个监测断面持续采集水位、浊度与水流等级，通过 MQTT 实时推送到 Web 监测台、移动端（现场巡查）与 3D 河道场景三端：

- **实时监测**：三断面状态卡、3D 河道水位柱随数据实时变化
- **智能预警**：按统一判级规则（洪水预警 / 高水位警戒 / 水质浑浊）自动判级，事件按 OPEN → HANDLING → RECOVERED 状态机流转
- **优先关注**：环境分 + 感知分 + 持续分加权，自动标出当前最需要关注的断面
- **多端协同**：事件与干预动作经 MQTT 跨端广播，Web 与移动端状态实时一致
- **规则/ML 对照**：IsolationForest 基于历史数据学习每个断面的正常形态，与固定规则对照裁决（默认权重 0.7 / 0.3）
- **多模态交互**：语音指令（ASR）、结论朗读（TTS）、现场拍照记录（Camera）

完整契约与验收标准见 `contract.md`。

## 2. 环境要求

| 组件 | 版本（实测可用） | 说明 |
| --- | --- | --- |
| Python | 3.13.9 | 运行 simulator.py / analyze.py / ml_detect.py |
| Mosquitto | 2.1.2 | MQTT Broker，双监听 1883 + 8083 |
| 浏览器 | Chrome / Edge 最新版 | 三端页面；ASR/TTS/摄像头仅 Chrome 系支持（Firefox 不支持 Web Speech API） |
| Python 依赖 | paho-mqtt 2.1.0、pandas 3.0.6、scikit-learn 1.9.1、numpy 2.5.3、matplotlib 3.11.2 | 见第 4 节 |

前端库（mqtt.js、three.js、OrbitControls）已本地化到各目录，不需要 npm、不依赖 CDN、不依赖外网。

## 3. 项目目录结构

```
nova-tidewatch-final-2026/
├── contract.md          # 统一契约（判级规则、状态机、Topic、验收标准）
├── README.md
├── web/                 # Web 监测台（三断面卡片、事件列表、优先关注、D5 对照、多模态、测试面板）
│   ├── index.html
│   ├── mqtt.min.js      # 本地化 mqtt.js
│   └── d5_compare.json  # D5 对照数据（由 python/ml_detect.py 自动生成）
├── mobile/              # 移动端现场巡查（优先关注断面 + 大按钮干预）
│   ├── index.html
│   └── mqtt.min.js
├── map3d/               # 3D 河道场景（Three.js，水位柱/水流动画/事件图标）
│   ├── index.html
│   ├── three.min.js     # r128 本地化
│   ├── OrbitControls.js
│   └── mqtt.min.js
├── mqtt/
│   ├── mosquitto.conf   # Broker 配置：1883 MQTT + 8083 WebSocket，匿名访问
│   └── simulator.py     # 模拟节点：3 断面 × 3 轮发 MQTT，同时追加历史 CSV
├── python/
│   ├── analyze.py       # 离线分析链：读历史 CSV，输出 report/report.html
│   └── ml_detect.py     # D5：IsolationForest 训练 + 规则/ML 对照 → web/d5_compare.json
├── data/
│   └── tidewatch_history.csv  # 历史数据（simulator 运行累积，ml_detect/analyze 的输入）
├── report/              # 离线分析输出（report.html、img/）
├── perception/          # 感知链路预留目录（当前 flowLevel 来源为 simulated）
└── Evidence/            # 各阶段验收证据（D1–D5、E1–E3 等，各目录附 README）
```

## 4. 依赖安装

```powershell
python -m pip install paho-mqtt pandas scikit-learn numpy matplotlib
```

Mosquitto 安装后需确认 `mosquitto` 在 PATH 中（`mosquitto -h` 能输出版本号）。前端库无需安装，仓库已含本地副本。

## 5. 完整启动顺序

全部命令在项目根目录运行：

1. **启动 Broker**（终端 1）：

   ```powershell
   mosquitto -c mqtt/mosquitto.conf -v
   ```

   看到 `Opening ipv4 listen socket on port 1883` 和 `Opening websockets listen socket on port 8083` 即为成功。

2. **运行模拟节点**（终端 2，约 30 秒发完一轮）：

   ```powershell
   python mqtt/simulator.py
   ```

3. **启动静态服务器**（终端 3，供三端页面访问）：

   ```powershell
   python -m http.server 8000
   ```

4. **打开三个端**（浏览器，均在 8000 端口）：
   - Web 监测台：<http://localhost:8000/web/index.html>
   - 移动端：<http://localhost:8000/mobile/index.html>（建议 DevTools 切手机视图）
   - 3D 场景：<http://localhost:8000/map3d/index.html>

> D5 对照区要求页面经 http 打开，不要直接双击 index.html。

## 6. Broker、端口与 Topic

| 项 | 值 |
| --- | --- |
| Broker 地址 | localhost |
| MQTT 端口 | 1883（mosquitto.conf listener 1883） |
| WebSocket 端口 | 8083（listener 8083，浏览器端用 `ws://localhost:8083`） |
| QoS | 1 |
| 匿名访问 | allow_anonymous true |

Topic 结构：

| Topic | 方向 | 载荷要点 |
| --- | --- | --- |
| `tidewatch/{reachId}/state` | 模拟节点/任意端 → 三端 | 统一 JSON 字段：reachId, waterLevel, turbidity, flowLevel, status, time |
| `tidewatch/event/update` | Web（事件权威端）→ 移动端/3D | 事件完整字段（event_id, reachId, start_time, problem, priority_reason, action, verify_data, state, recover_time） |
| `tidewatch/intervention` | Web ↔ 移动端 | { event_id, reachId, action }，action ∈ 开闸泄洪 / 开启泵站 / 投加净水剂 |

三端均订阅 `tidewatch/+/state`；去重优先用 message_id，否则按 reachId + time + 载荷哈希（event_id 不参与去重）。

## 7. 如何产生一条测试数据

三种方式任选：

**方式 A：模拟节点一轮**（9 条）

```powershell
python mqtt/simulator.py
```

每条载荷示例（status 由规则计算，不可手填）：

```json
{"reachId": "reach-b", "waterLevel": 9.0, "turbidity": 20, "flowLevel": 2, "status": "洪水预警", "time": "2026-10-04 21:00:00"}
```

**方式 B：Web 测试面板"手动发布"表单**

打开 Web 页 → 测试面板 → 选 reachId、填 waterLevel / turbidity、选 flowLevel → 点"发布"。status 与 time 由页面按规则和当前时间自动生成。

**方式 C：mosquitto_pub 单条**（PowerShell / Git Bash 均可）

```powershell
mosquitto_pub -h localhost -p 1883 -t tidewatch/reach-a/state -m '{"reachId":"reach-a","waterLevel":8.0,"turbidity":20,"flowLevel":2,"status":"高水位警戒","time":"2026-10-04 21:00:00"}'
```

注意：status 必须符合判级规则（waterLevel≥8.5 洪水预警；≥7.0 高水位警戒；turbidity≥60 水质浑浊；否则正常），且 time 必须晚于该断面最新消息，否则会被页面按契约拒绝或丢弃。

## 8. 如何验证 Web-移动端实时同步

1. 按第 5 节启动 Broker + 模拟节点 + 服务器，打开 Web 与移动端两页
2. 模拟器第 1 轮后，Web 与移动端"当前优先关注"均为 reach-b（洪水预警，优先分最高）；第 3 轮后变为 reach-a（高水位警戒，持续分累积）
3. Web 端事件列表出现 OPEN 事件 → 点"开始干预"选任一动作 → 该事件变"处理中"；**移动端同一事件同步变"处理中"**（订阅 tidewatch/event/update + tidewatch/intervention）
4. 反向：移动端对 OPEN 事件点大按钮干预 → **Web 端同一事件同步变 HANDLING**
5. 用 Web 手动发布恢复值（如 reach-b：6.5 / 20 / 1）→ 两端事件同时变"已恢复"并显示恢复时间
6. 重复干预与迟到消息：RECOVERED 后两端均拒绝任何回退（状态机单调守卫）

## 9. D1–D5 快速复现步骤

**D1 多断面稳定运行**：启动 Broker + 模拟节点 + 三端 → 三端均显示"已连接"；Web 三张断面卡片、移动端优先关注、3D 三个河段同时在线，模拟器 3 轮数据期间状态持续更新（Evidence/D1）。

**D2 持续风险与优先关注**：观察 Web 顶部"当前优先关注"随数据变化（第 1 轮 reach-b、第 3 轮 reach-a）；用手动发布改变某断面数值，观察优先分（环境+感知+持续）与高亮卡片切换（Evidence/D2）。

**D3 事件状态机与消息健壮性**：
1. 正常 → 异常消息自动创建 OPEN 事件（水位/水质/水流异常可多选记录）
2. 点"开始干预"选动作 → HANDLING，verify_data 持续追加新数据
3. 手动发布满足恢复条件的值 → 数据触发 RECOVERED（按钮不能直接恢复）
4. 测试面板"发送重复数据"观察重复丢弃计数、"发送旧数据"观察乱序/迟到处理；RECOVERED 不回滚（Evidence/D3）

**D4 故障与修复**：测试面板点"发送错误 Topic"（发往 tidewatch/wrong-topic/state）与"发送错误 JSON"，顶部统计"拒绝: N"递增并显示最近拒绝原因，系统状态不受破坏（Evidence/D4）。修复验证：点"发送带 message_id 的消息"或跑 simulator，三端恢复正常更新。

**D5 规则/ML 对照**：

```powershell
python python/ml_detect.py          # 训练 IsolationForest → web/d5_compare.json
```

经 http 打开 Web 页，观察"D5 规则/ML 对照"表格：每条消息的规则判断 / ML 判断 / 是否一致 / 组合裁决，不一致行红底；构造案例区含 2 个标注案例（规则正常 vs ML 明显异常 → 需人工复核）。手动发布 reach-a (6.8, 45, 2) 可实时复现该案例。权重由 `python/ml_detect.py` 写入 `web/d5_compare.json` 的 `rule_weight` / `ml_weight`；修改 `ml_detect.py` 中的权重并重跑可验证；也可直接改 `web/index.html` 的 `RULE_WEIGHT / ML_WEIGHT` 常量（Evidence/D5）。

## 10. 正常情况下应看到什么

- **Web**：顶部"当前优先关注：reach-b（优先分 N）"+ 金色高亮卡片；三张断面卡片实时刷新水位/浊度/水流/状态；事件列表随数据流转 OPEN → 处理中 → 已恢复；统计行"已处理消息"递增、重复/迟到/拒绝计数在点测试按钮时递增；D5 对照表逐断面更新
- **移动端**：只显示优先关注断面的环境结论与大按钮；OPEN 事件出现 3 个大干预按钮；RECOVERED 显示"已恢复"
- **3D**：三个河段水位柱随 waterLevel 升降，水面颜色随状态（绿正常/橙警戒/红洪水/紫浑浊），泡沫流速随 flowLevel，优先关注断面带金色脉动光环，事件图标红/橙闪烁或绿常亮，点击河段出详情面板
- **终端**：模拟器每 3 秒打印一条 published 载荷；Broker 日志显示三端订阅与消息分发

## 11. 常见问题与排查

| 现象 | 原因与处理 |
| --- | --- |
| 页面"未连接" | 先确认 Broker 已启动且 1883/8083 在监听：`netstat -ano \| findstr 1883`；确认页面在 http 下打开、`web/mqtt.min.js` 存在（页面有"mqtt.js 加载失败"红色提示兜底） |
| mosquitto 启动报端口占用 | 已有一个实例在跑，直接复用即可；或先结束旧进程 |
| D5 区显示"对照数据加载失败" | 两种原因：① 用 file:// 直接双击打开页面（Chrome 拦 fetch）→ 用 `python -m http.server 8000` 后访问；② 未运行 `python python/ml_detect.py` 生成 `web/d5_compare.json` |
| 语音按钮弹"浏览器不支持" | Web Speech API 仅 Chrome/Edge 支持；且需授权麦克风 |
| 拍照无反应 | 摄像头权限被拒；或浏览器不支持 getUserMedia（需 https 或 localhost/file，Chrome/Edge 均可） |
| 手动发布/旧数据被丢弃 | 按契约预期：time 不晚于该断面最新消息 → 乱序丢弃；载荷完全相同 → 重复丢弃；字段缺失/格式错 → 拒绝并计数 |
| 控制台中文乱码 | Windows 控制台编码问题，加环境变量再跑：`$env:PYTHONIOENCODING="utf-8"` |
| CSV 首行粘连 | 手写历史末尾无换行时模拟器追加行会粘连，`ml_detect.py` / `analyze.py` 读取时自动修复（不改原文件）。建议只用 simulator 生成 CSV，不要手写 |

## 12. 已知限制

- flowLevel 本阶段来源为 simulated（contract 4.3）：无真实视觉模型，感知记录 confidence 恒为 null，不伪造置信度
- ASR/TTS 依赖 Web Speech API，仅 Chrome/Edge；拍照/语音均需用户授权
- D5 对照区依赖 fetch，必须经 http 访问页面
- IsolationForest 每断面训练样本量小（数十条），标签阈值是固定定义；历史数据累积后重跑 `python python/ml_detect.py` 即可更新对照
- 事件、去重集合、照片均为页面内存态，刷新页面即重置（无后端持久化）
- 移动端按巡查分工只显示优先关注断面，不显示全部断面列表
- RECOVERED 事件按契约锁定，后续消息不回退
- 摄像头照片默认只存内存，需点"保存图片"手动下载

## 13. 使用的开源库 / 模型 / 资料来源

| 组件 | 用途 | 许可/来源 |
| --- | --- | --- |
| Eclipse Mosquitto 2.1.2 | MQTT Broker（1883 + WebSocket 8083） | EPL/EDL |
| mqtt.js（各端本地 mqtt.min.js） | 浏览器 MQTT 客户端（WS 连接） | MIT |
| Three.js r128 + OrbitControls | 3D 河道场景与相机控制 | MIT（本地化） |
| pandas / numpy | 历史数据读取与数值处理 | BSD |
| scikit-learn（IsolationForest） | D5 每断面异常形态学习 | BSD |
| matplotlib | analyze.py 离线分析图表 | PSF-based license |
| paho-mqtt 2.1.0 | 模拟节点 MQTT 发布 | EPL/EDL |
| Web Speech API（SpeechRecognition / SpeechSynthesis） | ASR 语音指令、TTS 结论朗读 | Chrome 内置 |
| getUserMedia + Canvas | 现场拍照与感知记录 | 浏览器内置 |

数据来源：`contract.md` 第 3 节演示数据（reach-a/b/c 各 3 组）+ `mqtt/simulator.py` 生成的模拟序列，历史累积于 `data/tidewatch_history.csv`。
