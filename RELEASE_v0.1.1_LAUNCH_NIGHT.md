# v0.1.1 — Launch Night Release: Grow a Self from Memory
# v0.1.1 —— 发布夜版本：让“自我”从记忆中生长

loam is not a persona prompt pack; it is a memory runtime for long-horizon identity continuity.
loam 不是提示词人设包，而是一个面向长期身份连续性的记忆运行时。

This release focuses on one thing: making growth explainable, reproducible, and deployable.
这个版本聚焦一件事：让“生长”可解释、可复现、可部署。

---

## Why this release exists
## 为什么发布这个版本

Most character systems drift because they keep rewriting summaries of summaries.
多数角色系统会漂移，因为它们在“总结的总结”中不断重写自己。

We anchor updates to immutable raw turns, so identity change has evidence and traceability.
我们把更新锚定到不可变原始轮次，让身份变化有证据可追溯。

The goal is not louder personality performance, but stable growth from lived interaction.
目标不是更“会演”的人格表现，而是从真实互动中稳定生长。

---

## Core breakthroughs
## 核心突破点

No-snowball invariant: new identity updates do not recursively depend on old persona summaries.
非滚雪球不变量：新的身份更新不递归依赖旧的人格总结。

Forced memory pipeline: every turn follows `/context -> upstream -> /ingest`.
强制记忆流水线：每轮固定执行 `/context -> upstream -> /ingest`。

Gated growth dynamics: evidence accumulates before committing trait shifts.
门控生长动力学：证据先累积，再提交特质变化。

Behavior-grounded calibration: repeated “saying” cannot replace repeated “doing”.
行为落地校准：反复“说自己是”不能替代反复“实际表现”。

Single local endpoint + multi-upstream routing keeps integration simple and vendor-agnostic.
单本地入口 + 多上游路由，让接入简单且不锁定供应商。

Dual-model decoupling separates response quality from growth quality.
双模型解耦把“回复质量”和“生长质量”解耦处理。

---

## Growth formula (quantitative accumulation -> qualitative shift)
## 生长公式（量变积累 -> 质变跃迁）

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

Evidence stays in `pending` until it crosses gate, then a trait shift is committed.
证据会先停留在 `pending`，跨过门槛后才提交为特质跃迁。

Inspiration note: “Dao gives birth to one, one to two, two to three, three to all things.”
灵感注记：“道生一，一生二，二生三，三生万物。”

In engineering terms, this maps to staged emergence from seed signals to structured identity layers.
在工程语义里，这对应从萌芽信号到层级化身份结构的分阶段涌现。

---

## Beginner-ready deployment path
## 面向小白的可执行部署路径

Install dependencies in Termux: `python`, `git`, and `curl`.
在 Termux 先安装依赖：`python`、`git`、`curl`。

Clone repo, prepare `~/.loam/upstreams.json`, then run one-command startup.
拉取仓库、准备 `~/.loam/upstreams.json`，然后执行一键启动。

Set Agent Base URL to `http://127.0.0.1:8780/v1`.
把 Agent 的 Base URL 设置为 `http://127.0.0.1:8780/v1`。

Use model format `provider/model`, for example `relayA/gpt-4o-mini`.
模型名使用 `provider/model` 格式，例如 `relayA/gpt-4o-mini`。

---

## URL/API security statement
## URL/API 安全声明

Provider keys are configured in your local runtime files or environment variables.
上游 key 配置在你本地运行环境的文件或环境变量中。

Requests are sent from your local process to your selected upstream providers.
请求由你的本地进程发往你自己选择的上游提供方。

loam does not require sending your provider keys to project maintainers.
loam 不要求把你的上游 key 发送给项目维护者。

Normal operation does not depend on a mandatory maintainer-hosted cloud endpoint.
常规运行不依赖维护者托管的强制云端端点。

---

## Included in this release
## 本版本包含内容

Core runtime modules for store, digest, growth, context, server, and CLI.
核心运行时模块：store、digest、growth、context、server、CLI。

OpenAI-compatible forced-flow proxy with multi-upstream support.
支持多上游的 OpenAI 兼容强制流程代理。

Termux scripts for startup, status, stop, and daily operations.
覆盖启动、状态、停止、日常运维的 Termux 脚本。

Updated beginner documentation with detailed “where to run / what to fill / why to fill”.
更新小白文档，明确“在哪运行 / 填什么 / 为什么填”。

---

## Final note
## 最后说明

This release is a baseline for identity systems that need memory permanence and controlled growth.
这个版本是“记忆永久化 + 可控生长”身份系统的可用基线。

Do not script a persona; build a self that can be traced back to experience.
不要脚本化“人设”；要构建一个能追溯到经历本身的“自我”。