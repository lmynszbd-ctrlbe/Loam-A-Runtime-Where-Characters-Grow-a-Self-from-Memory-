# v0.1.0 — loam Final Runtime Release

Not a persona script engine, but a memory-growth runtime.
这不是一个人设脚本引擎，而是一个记忆生长运行时。

Identity grows from lived dialogue, not from static prompt cards.
身份从真实对话中生长，而不是从静态提示词卡片中生成。

---

## Why this release matters
## 为什么这个版本重要

Most persona systems drift because they recursively rewrite summaries.
多数人格系统会漂移，因为它们在循环改写总结。

loam avoids that drift by anchoring every meaningful change to immutable raw turns.
loam 通过把每次关键变化锚定到不可变原始轮次来避免漂移。

The result is continuity with accountability.
结果是：连续性与可追责性同时成立。

---

## Breakthrough ideas in this version
## 本版本的突破点

### 1) No-snowball growth invariant
### 1）非滚雪球生长不变量

We do not treat yesterday’s persona summary as today’s truth source.
我们不把昨天的人格总结当作今天的真相源。

Raw dialogue remains the first-class source of evidence.
原始对话始终是一等证据源。

### 2) Quantitative-to-qualitative growth formula
### 2）量变到质变的生长公式

Growth speed is endogenous and phase-aware, not externally rate-limited.
生长速度是内生且分阶段的，而不是外部硬限速。

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

Evidence accumulates in `pending`; commit occurs only when gate is crossed.
证据先在 `pending` 累积；只有越过门槛才会提交变化。

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

This creates progressive accumulation instead of sudden uncontrolled jumps.
这保证了渐进累积，而不是失控式突增。

Repeated weak signals can still produce phase transition over long horizons.
重复弱信号在长时间尺度上依然可以触发阶段跃迁。

### 3) Controlled breakthrough channel
### 3）受控突破通道

Major events can bypass consolidation resistance without breaking stability.
重大事件可以突破固化阻力，同时不破坏整体稳定性。

`if salience >= BREAKTHROUGH: delta += gain * signal * (salience - BREAKTHROUGH)`
`if salience >= BREAKTHROUGH: delta += gain * signal * (salience - BREAKTHROUGH)`

### 4) Behavior-grounded calibration
### 4）行为落地校准

Trait strength is calibrated toward observed behavior frequency.
特质强度会向真实行为频率校准。

This blocks performative self-description from inflating identity unrealistically.
这阻止“口头自我描述”脱离行为现实而虚高。

### 5) Forced ingest architecture for unreliable tool-calling
### 5）应对工具不稳定调用的强制入库架构

Pipeline is enforced in proxy: recall -> generate -> ingest every turn.
流水线由代理强制执行：每轮都“回忆 -> 生成 -> 入库”。

Memory write does not depend on whether an Agent decides to call tools.
记忆写入不依赖 Agent 是否“恰好调用工具”。

### 6) Single endpoint, multi-upstream routing
### 6）单入口多上游路由

Keep one Agent URL and route by `provider/model`.
Agent 只保留一个 URL，通过 `provider/model` 路由。

This decouples user-facing integration from upstream vendor switching.
这把用户侧接入与上游厂商切换彻底解耦。

### 7) Dual-model decoupling
### 7）双模型解耦

Chat model and growth model are independently configurable.
聊天模型与生长模型可独立配置。

Identity continuity survives provider/model replacement.
身份连续性不随上游模型替换而丢失。

---

## Included in v0.1.0
## v0.1.0 包含内容

Core runtime (`loam/`) with store/core/mind/server/CLI.
核心运行时（`loam/`），含 store/core/mind/server/CLI。

Forced-flow OpenAI-compatible proxy (`bridge/forced_flow_proxy.py`).
强制流程 OpenAI 兼容代理（`bridge/forced_flow_proxy.py`）。

Termux operation scripts for start/status/stop/log/final orchestration.
Termux 启停/状态/日志/总控脚本全套。

Integration and smoke validation scripts.
集成与冒烟验证脚本。

Deployment and integration docs.
部署与接入文档。

---

## Quick start
## 快速启动

`cd ~/loam && LOAM_API_KEY='your_key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`
`cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh`

`bash scripts/termux/final_status_all.sh`
`bash scripts/termux/final_status_all.sh`

`bash scripts/termux/final_stop_all.sh`
`bash scripts/termux/final_stop_all.sh`

---

## Security note
## 安全说明

If any token was exposed in chat/logs, revoke and rotate immediately.
若 token 曾出现在聊天或日志中，请立即吊销并轮换。