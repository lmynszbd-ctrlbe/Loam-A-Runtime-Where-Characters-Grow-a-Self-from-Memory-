# loam — 不是“写人设”，而是“让角色从记忆长出自我”

A runtime where a character identity grows from memory instead of prompt scripting.
一个让角色身份从记忆中生长、而不是靠提示词脚本堆出来的运行时。

Growth is anchored in raw dialogue, not in recursively rewritten summaries.
生长锚定在原始对话，而不是在反复改写的“上一版总结”里。

This project is designed for long-term continuity, auditability, and model portability.
这个项目面向长期连续性、可审计性和模型可迁移性而设计。

---

## ⚡ Key Highlights
## ⚡ 重点亮点

No-snowball personality evolution: we do not feed the previous persona snapshot as ground truth.
非滚雪球人格演化：我们不把上一版人格快照继续喂回去当真相。

Immutable L0 anchor: every trait change must be traceable to raw user/assistant turns.
不可变 L0 锚点：每一次特质变化都必须可追溯到原始 user/assistant 轮次。

Forced raw-ingest pipeline: `/context -> upstream model -> /ingest` is enforced by proxy, not by tool-call luck.
强制原文入库流水线：`/context -> 上游模型 -> /ingest` 由代理强制执行，不吃“工具调用概率”。

Single URL, multi-upstream routing: switch providers via `provider/model` while keeping one Agent base URL.
单入口多上游路由：Agent 只填一个 URL，用 `provider/model` 在多家渠道间切换。

Dual-model decoupling: chat model and growth model are independently configurable.
双模型解耦：前台聊天模型与后台生长模型可独立配置。

---

## 🌱 Growth Mechanics (Quantitative Change -> Qualitative Shift)
## 🌱 生长机制（量变 -> 质变）

Trait plasticity follows an endogenous capacity curve instead of external hard throttling.
特质可塑性遵循内生容量曲线，而不是外部硬限速。

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

Evidence is accumulated in `pending`; only when `|pending| >= gate` does a commit happen.
证据先累积到 `pending`；只有当 `|pending| >= gate` 时才提交变化。

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

This hysteresis gate is the core reason changes are progressive rather than abrupt spikes.
迟滞门控是“循序渐进而非突增暴冲”的核心原因。

Repeated weak signals can eventually cross the gate, producing phase transition over time.
重复的弱信号也能最终越过门槛，长期触发阶段跃迁。

Breakthrough events can bypass consolidation resistance in a controlled way.
重大事件可以在受控条件下突破固化阻力。

`if salience >= BREAKTHROUGH: delta += gain * signal * (salience - BREAKTHROUGH)`
`if salience >= BREAKTHROUGH: delta += gain * signal * (salience - BREAKTHROUGH)`

Expression-feedback calibration pulls trait strength toward observed behavior frequency.
表达反馈校准会把特质强度拉向真实行为频率。

This prevents performative self-description from inflating identity unrealistically.
这能防止“口头人设”脱离行为现实而虚高膨胀。

---

## 🧠 Why this is different
## 🧠 为什么这套方案更新鲜

Most systems summarize then summarize again; drift compounds over time.
多数系统是“总结再总结”；漂移会随时间被放大。

loam preserves raw turns as primary truth and treats derived layers as rebuildable projections.
loam 把原始轮次作为一等真相，把派生层视为可重建投影。

The system can rotate providers/models without losing identity continuity.
系统可以更换上游和模型而不丢身份连续性。

Auditability is not a dashboard add-on; it is a storage and update invariant.
可审计性不是后加看板，而是存储与更新规则本身。

---

## 🚀 Termux One-Command Start
## 🚀 Termux 一条命令启动

Before start, configure upstream mapping at `~/.loam/upstreams.json`.
启动前先在 `~/.loam/upstreams.json` 配好上游映射。

`cd ~/loam && LOAM_API_KEY='your_key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`
`cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`

Use `bash scripts/termux/final_status_all.sh` to check health.
用 `bash scripts/termux/final_status_all.sh` 查看健康状态。

Use `bash scripts/termux/final_stop_all.sh` to stop all services.
用 `bash scripts/termux/final_stop_all.sh` 停止全部服务。

---

## 🔌 Agent Integration
## 🔌 Agent 接入

Set Agent Base URL to `http://<host>:8780/v1`.
把 Agent 的 Base URL 设置为 `http://<主机>:8780/v1`。

Pick model as `provider/model` (example: `relayB/deepseek-chat`).
模型使用 `provider/model`（例如：`relayB/deepseek-chat`）。

The proxy enforces recall + generation + raw ingest on every turn.
代理会在每轮强制执行“回忆 -> 生成 -> 原文入库”。

---

## ✅ Verification
## ✅ 验证

`python tests/test_integration.py && python e2e_smoke.py`
`python tests/test_integration.py && python e2e_smoke.py`

---

Don’t script a persona. Grow a self.
别写人设，让“我”长出来。