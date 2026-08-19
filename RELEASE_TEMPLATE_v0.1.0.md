# v0.1.0 — loam Final Runtime Release

Identity growth is engineered, not hand-scripted.
身份生长是被工程化实现的，而不是手写脚本拼出来的。

“Dao gives birth to one, one to two, two to three, three to all things.”
“道生一，一生二，二生三，三生万物。”

In this release, the quote maps to a concrete growth pipeline from accumulation to phase shift.
在这个版本里，这句话对应的是“从累积到跃迁”的具体生长流水线。

---

## Why this release matters
## 为什么这个版本重要

Most persona systems drift because they repeatedly summarize summaries.
多数人格系统会漂移，因为它们在“总结的总结”里循环自改。

loam anchors change to immutable raw turns and keeps derived layers rebuildable.
loam 把变化锚定到不可变原始轮次，并让派生层始终可重建。

This gives continuity without blind self-reinforcement.
这让系统在保持连续性的同时避免盲目自我强化。

---

## Breakthrough highlights
## 突破亮点

No-snowball invariant: yesterday’s persona snapshot is not today’s truth source.
非滚雪球不变量：昨天的人格快照不是今天的真相来源。

Gated growth dynamics: incremental evidence accumulates before committing change.
门控生长动力学：增量证据先积累，再提交变化。

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

Quantitative accumulation can produce qualitative phase transition over time.
量变可以在时间尺度上触发质变。

Controlled breakthrough channel allows major events to move consolidated traits safely.
受控突破通道允许重大事件在安全边界内推动固化特质。

Behavior-grounded calibration prevents performative identity inflation.
行为落地校准可防止“表演型人格”虚高膨胀。

Forced ingest pipeline guarantees memory write even when tool-calling is unreliable.
强制入库流水线可在工具调用不稳定时仍保证记忆写入。

Single endpoint plus multi-upstream routing keeps integration simple and vendor-agnostic.
单入口加多上游路由让接入保持简单且不锁定供应商。

Dual-model decoupling keeps chat response model separate from growth model.
双模型解耦让聊天回复模型与生长模型彼此独立。

---

## Security note for API/URL concerns
## 面向 API/URL 顾虑的安全说明

Your API keys are configured and stored in your own runtime environment.
你的 API key 在你自己的运行环境里配置与存储。

Requests are sent from your local process directly to your chosen upstream providers.
请求由你的本地进程直接发往你选择的上游提供方。

loam does not require forwarding your keys to project maintainers.
loam 不要求你把 key 转发给项目维护者。

No project-owned remote memory endpoint is required for normal operation.
正常运行不依赖“项目方托管的远程记忆端点”。

---

## Included in v0.1.0
## v0.1.0 包含内容

Core runtime in `loam/` with store, growth, digest, context, server, and CLI.
`loam/` 核心运行时，包含 store、growth、digest、context、server 与 CLI。

Forced-flow OpenAI-compatible proxy in `bridge/forced_flow_proxy.py`.
`bridge/forced_flow_proxy.py` 中提供强制流程 OpenAI 兼容代理。

Termux scripts for one-command start, status, stop, and orchestration.
Termux 脚本覆盖一键启动、状态查看、停止与总控。

Integration and smoke tests for deployment confidence.
集成与冒烟测试用于上线可信验证。

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