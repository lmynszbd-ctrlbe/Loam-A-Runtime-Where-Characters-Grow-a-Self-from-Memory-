# v0.1.0 — loam Final Runtime Release

Identity growth is engineered from memory evidence, not hand-written persona scripts.
身份生长来自可追溯记忆证据，而不是手写人设脚本。

---

## Why this release matters
## 为什么这个版本重要

Most persona systems drift because they repeatedly summarize previous summaries.
多数人格系统会漂移，因为它们不断对“上一层总结”再做总结。

loam anchors updates to immutable raw turns and keeps derived layers rebuildable.
loam 把更新锚定到不可变原始轮次，并让派生层保持可重建。

This gives long-horizon continuity without recursive identity inflation.
这让系统在长期运行里保持连续性，同时避免递归放大的人格膨胀。

---

## Breakthrough highlights
## 突破亮点

No-snowball invariant: yesterday’s persona snapshot is not today’s truth source.
非滚雪球不变量：昨天的人格快照不是今天的真相来源。

Forced memory pipeline: every turn follows `/context -> upstream -> /ingest`.
强制记忆流水线：每轮都执行 `/context -> upstream -> /ingest`。

Multi-upstream routing with single local endpoint keeps integration stable and vendor-agnostic.
单本地入口 + 多上游路由，既稳定接入又不锁定供应商。

Behavior-grounded calibration suppresses performative trait inflation.
行为落地校准可抑制“表演型特质”虚高。

Dual-model decoupling separates chat response model from growth model.
双模型解耦把聊天回复模型与生长模型分离。

---

## Growth formula (quantitative -> qualitative)
## 生长公式（量变 -> 质变）

Capacity:
容量：

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

Per-event update:
单事件更新：

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

Gate threshold:
门控阈值：

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

Evidence accumulates in `pending` before crossing gate and committing a trait shift.
证据先在 `pending` 累积，跨过门槛后才提交特质跃迁。

Inspiration note: “道生一，一生二，二生三，三生万物” is used here as a growth metaphor from seed to layered emergence.
灵感注记：“道生一，一生二，二生三，三生万物”在此作为从萌芽到层级涌现的生长隐喻。

---

## Security note for API/URL concerns
## 面向 API/URL 顾虑的安全说明

Provider keys are configured in local files/env on user-owned runtime.
上游 key 配置在用户自有运行环境的本地文件/环境变量中。

Requests are sent from local process to selected upstream providers.
请求由本地进程发往用户自己选择的上游提供方。

loam does not require sending provider keys to project maintainers.
loam 不要求将上游 key 发送给项目维护者。

Normal operation does not depend on a maintainer-controlled mandatory cloud endpoint.
常规运行不依赖维护者托管的强制云端端点。

---

## Included in v0.1.0
## v0.1.0 包含内容

Core runtime (`store`, `growth`, `digest`, `context`, `server`, `cli`).
核心运行时（`store`、`growth`、`digest`、`context`、`server`、`cli`）。

Forced-flow OpenAI-compatible proxy (`bridge/forced_flow_proxy.py`).
强制流程 OpenAI 兼容代理（`bridge/forced_flow_proxy.py`）。

Termux startup and management scripts for deployable operation.
可部署运行的 Termux 启停与管理脚本。

Integration and smoke paths for pre-release verification.
上线前可执行的集成与冒烟验证路径。

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

If any token was exposed, revoke and rotate immediately.
如有 token 暴露，请立刻吊销并轮换。