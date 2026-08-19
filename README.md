# loam — 不是“写人设”，而是“让角色从记忆长出自我”

A runtime where identity grows from memory instead of prompt scripts.
一个让身份从记忆里生长、而不是靠提示词脚本拼装的运行时。

“Dao gives birth to one, one gives birth to two, two gives birth to three, three gives birth to all things.”
“道生一，一生二，二生三，三生万物。”

In loam, this is implemented as engineering, not metaphor.
在 loam 里，这句话被实现成工程机制，而不只是比喻。

---

## Core Positioning
## 核心定位

No-snowball evolution: we do not recursively overwrite identity with identity summaries.
非滚雪球演化：我们不把“人格总结”反复喂回去覆盖人格本身。

Raw-turn anchoring: meaningful updates must point back to immutable L0 dialogue.
原始轮次锚定：关键更新必须能追溯到不可变的 L0 对话。

Progressive growth: quantitative accumulation triggers qualitative shifts through gating.
渐进生长：通过门控机制，让量变持续积累并触发质变。

Model decoupling: chat model and growth model can be configured independently.
模型解耦：前台聊天模型与后台生长模型可以独立配置。

---

## Key Breakthroughs
## 重点突破

Forced ingest pipeline is guaranteed by proxy, not by tool-call probability.
强制入库流水线由代理保证，不依赖“工具是否被调用”的概率。

Single endpoint supports multi-upstream routing by `provider/model`.
单入口支持按 `provider/model` 路由到多家上游。

Behavior-grounded calibration prevents performative persona inflation.
行为落地校准机制可防止“口头人设”虚高膨胀。

Breakthrough channel allows major events to move consolidated traits in a controlled way.
受控突破通道允许重大事件在稳定前提下推动已固化特质。

---

## Growth Formula (Quantitative -> Qualitative)
## 生长公式（量变 -> 质变）

Capacity is endogenous and phase-sensitive.
容量是内生且分阶段敏感的。

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

Per-event update uses signal and salience.
单次事件更新同时考虑方向与显著度。

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

Evidence accumulates in `pending`; commit occurs only after crossing gate.
证据先累积在 `pending`，跨过门槛才发生提交。

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

This prevents abrupt spikes and enables long-horizon phase transition.
这既抑制突增暴冲，也允许长期量变触发阶段跃迁。

---

## Security and Privacy
## 安全与隐私

Your API keys are stored locally on your own device/runtime by default.
你的 API key 默认存放在你自己的本地设备/运行环境中。

Keys are read by your local process and used only for direct upstream requests.
key 由本地进程读取，仅用于向你配置的上游发起直连请求。

loam does not require sending your keys to project maintainers.
loam 不要求把你的 key 发送给项目维护者。

By default, there is no built-in telemetry pipeline that uploads your secrets to us.
默认没有把你的密钥上报给我们这一侧的内置遥测通道。

You still need to trust your own host, client plugins, and chosen upstream providers.
你仍需信任你自己的主机环境、客户端插件以及所选上游服务商。

---

## One-Command Start (Termux)
## 一条命令启动（Termux）

Configure `~/.loam/upstreams.json` first, then run:
先配置 `~/.loam/upstreams.json`，再执行：

`cd ~/loam && LOAM_API_KEY='your_key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`
`cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`

Use status command to verify both loam and proxy are healthy.
用状态命令确认 loam 与代理都健康运行。

`bash scripts/termux/final_status_all.sh`
`bash scripts/termux/final_status_all.sh`

---

Don’t script a persona. Grow a self.
别写人设，让“我”长出来。