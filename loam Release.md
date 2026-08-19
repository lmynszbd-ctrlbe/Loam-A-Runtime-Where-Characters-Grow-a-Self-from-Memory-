# loam Release v0.1.1: Grow a Self from Memory

loam is a memory runtime for long-horizon identity continuity. Instead of repeatedly rewriting persona summaries, it keeps immutable raw turns, digests them into derived memory layers, and applies gated growth dynamics so identity change is evidence-driven, auditable, and reconstructable. This release is focused on turning that philosophy into practical deployment: stronger beginner docs, clearer routing model, clearer security boundary, and a release-ready narrative you can ship externally.

loam 是一个面向长期身份连续性的记忆运行时。它不依赖“总结套总结”来维持人格，而是保留不可变原始轮次，消化为可重建的派生记忆层，并通过门控生长动力学让身份变化由证据驱动、可审计、可复现。本次发布重点是把这套理念落到可部署层面：补强小白文档、明确路由机制、明确安全边界，并提供可直接对外发布的叙事版本。

---

## Core breakthroughs

The first breakthrough is the no-snowball invariant: meaningful updates must anchor to raw dialogue evidence, not to recursive persona snapshots. The second is forced memory pipeline enforcement (`/context -> upstream -> /ingest`) through local proxy, so memory write reliability no longer depends on host tool-calling luck. The third is gated growth behavior where quantitative accumulation in pending state leads to qualitative shifts only after threshold crossing, preventing random spikes while preserving long-term emergence. The fourth is model-routing flexibility: one local endpoint can route to multiple upstream providers with explicit `provider/model` naming.

第一项突破是“非滚雪球不变量”：关键更新必须锚定原始对话证据，而不是递归人格快照。第二项是通过本地代理强制执行记忆流水线（`/context -> upstream -> /ingest`），让记忆写入不再依赖宿主工具调用运气。第三项是门控生长：证据先在 pending 中量变累积，跨阈值后再发生质变，既避免随机暴冲，又保留长期涌现。第四项是模型路由弹性：单一本地入口可按 `provider/model` 显式路由到多上游。

---

## Growth formula and inspiration mapping

Trait dynamics in this runtime are encoded by capacity, delta, and gate terms: `capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`, `delta = plasticity * capacity * signal * salience`, and `gate = max(gate_floor, gate_ratio * capacity)`. In operation, evidence accumulates before commit, which gives the system progressive adaptation instead of abrupt instability. The phrase “Dao gives birth to one, one to two, two to three, three to all things” is used here as an inspiration mapping for staged emergence from seed signals to structured identity layers.

本运行时的特质动力学由 capacity、delta、gate 三项描述：`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`、`delta = plasticity * capacity * signal * salience`、`gate = max(gate_floor, gate_ratio * capacity)`。在实际运行中，证据先累积再提交，因此系统表现为渐进适应而非突发失稳。“道生一，一生二，二生三，三生万物”在这里作为工程灵感映射，用于表达从萌芽信号到层级化身份结构的阶段性涌现。

---

## Deployment scope (not only Termux)

This release supports multiple deployment paths: Termux for mobile personal always-on usage, Linux server/VM for long-running managed operation, WSL/macOS for development and debugging, and containerized setups for reproducibility across teams. Across all modes, client requests should target local proxy endpoint and use provider-prefixed model naming so routing and memory flow remain deterministic.

本次发布支持多种部署路径：Termux（移动端个人常驻）、Linux 服务器/虚拟机（长期托管运行）、WSL/macOS（开发调试）、容器化（团队环境可复现）。无论哪种模式，客户端都应连接本地代理端点并使用带 provider 前缀的模型命名，以保证路由和记忆流水线确定可控。

---

## Deployment guide index

For practical deployment, use `FINAL_RELEASE.md` as the one-stop playbook, `DEPLOYMENT_MODES.md` for environment comparison, `TERMUX_QUICKSTART.md` for Android path, and `MULTI_UPSTREAM_QUICKSTART.md` for provider routing setup. This release explicitly supports more than Termux and keeps the same runtime semantics across all deployment modes.

实际部署请按以下索引：`FINAL_RELEASE.md`（总手册）、`DEPLOYMENT_MODES.md`（环境对比）、`TERMUX_QUICKSTART.md`（Android 路径）、`MULTI_UPSTREAM_QUICKSTART.md`（多上游路由配置）。本次发布明确不止支持 Termux，且在不同部署模式下保持一致运行语义。

---

## URL/API security boundary

Provider credentials are sourced from local runtime files or environment variables and used by local processes to call user-selected upstream providers. The project does not require uploading provider keys to maintainers, and normal operation does not depend on a maintainer-hosted mandatory cloud relay. Residual risk mainly comes from user-side host security, plugin chain trust, and secret handling discipline.

上游凭证来自本地运行环境的文件或环境变量，由本地进程发往用户选择的上游提供方。项目不要求把 provider key 上传给维护者，常规运行也不依赖维护者托管的强制云端中继。剩余风险主要来自用户侧主机安全、插件链路信任和密钥管理纪律。

---

## Included in this release

This release includes expanded deployment playbooks, rewritten beginner quickstarts, clarified multi-upstream routing instructions, revised third-party integration guidance, consolidated pre-launch checklist, and updated release assets aligned with launch-night messaging. Together these changes shift the project from “works in demos” to “deployable with clear operational expectations.”

本次发布包含：扩展后的部署总手册、重写的小白快速启动文档、明确化的多上游路由说明、更新后的第三方接入指南、整合后的上线前检查清单，以及与发布夜传播口径对齐的发布资产。这些改动共同推动项目从“演示可用”走向“可部署且运维预期清晰”。

---

## Highlight visual-content module (release page)

For the release page, use a four-card visual sequence: **Card 1: drift problem** (summary recursion vs raw-turn anchoring), **Card 2: enforced pipeline** (`/context -> upstream -> /ingest` flowchart), **Card 3: growth formula panel** (capacity/delta/gate with pending-to-commit transition), and **Card 4: deployment coverage** (Termux, Linux/VM, WSL/macOS, container). Keep each card to one image + one implication paragraph so launch-night readers can quickly map value to execution.

在发布页建议使用四卡图文结构：**卡片 1：漂移问题**（总结递归 vs 原始轮次锚定）、**卡片 2：强制流程**（`/context -> upstream -> /ingest` 流程图）、**卡片 3：生长公式面板**（capacity/delta/gate 与 pending->commit 过渡）、**卡片 4：部署覆盖**（Termux、Linux/VM、WSL/macOS、容器）。每张卡保持“一图 + 一段落地含义”，让发布夜读者快速完成“价值-执行”映射。

---

Do not hard-freeze a persona. Build a self that can be traced to experience.
不要写太固化的人设，要构建一个可追溯到真实经历的“自我”。