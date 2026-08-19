# v0.1.0 — loam Runtime Foundation Release

loam establishes a memory-first identity runtime where character continuity is built from immutable dialogue evidence rather than recursive persona scripting. The release baseline includes persistent memory storage, digest and growth cycles, context reconstruction, and a forced-flow proxy that keeps retrieval and ingest on every turn.

loam 构建的是“记忆优先”的身份运行时：角色连续性来自不可变对话证据，而不是递归人设脚本。该基础版本包含持久记忆存储、消化与生长循环、上下文重建能力，以及确保每轮都检索与入库的强制流程代理。

---

## Why this baseline matters

Most persona systems decay when they repeatedly summarize older summaries. loam avoids that by anchoring meaningful updates to raw turns and preserving rebuildability of derived layers. This makes identity changes explainable, reduces drift, and supports long-term operation under evolving model choices.

多数人格系统在“总结套总结”中逐步退化。loam 通过把关键更新锚定到原始轮次，并保持派生层可重建来规避这一问题。这样可让身份变化可解释、降低漂移，并在模型迭代下保持长期可运行。

---

## Technical highlights

This release introduces no-snowball update semantics, gated growth dynamics, and forced memory pipeline enforcement. Growth behavior is controlled by capacity, delta, and gate terms, so evidence accumulates progressively before crossing commitment thresholds. Combined with multi-upstream routing and model decoupling, the runtime remains both stable and vendor-flexible.

本版本引入非滚雪球更新语义、门控生长动力学和强制记忆流水线。生长行为由 capacity、delta、gate 项共同控制，证据先渐进累积，再跨阈值提交。叠加多上游路由和模型解耦后，运行时既稳定又具备供应商灵活性。

---

## Scope included

Included scope covers core runtime modules (`store`, `digest`, `growth`, `context`, `server`, `cli`), OpenAI-compatible forced-flow proxy, Termux operation scripts, and integration/testing assets for launch preparation. Teams can run this baseline directly or extend it into server-managed deployments.

本版本范围覆盖核心运行时模块（`store`、`digest`、`growth`、`context`、`server`、`cli`）、OpenAI 兼容强制流程代理、Termux 运维脚本，以及上线准备所需的接入与测试资产。团队可直接上线该基线，也可扩展到服务器托管部署。

---

## Quick start reference

Use `FINAL_RELEASE.md` for complete deployment playbook and mode comparison, then configure upstream mapping and run startup scripts. For release notes targeting launch events, use `RELEASE_v0.1.1_LAUNCH_NIGHT.md` as the public-facing long form.

部署时请先阅读 `FINAL_RELEASE.md`（完整流程与模式对比），再配置上游映射并执行启动脚本。若用于发布活动文案，可使用 `RELEASE_v0.1.1_LAUNCH_NIGHT.md` 作为对外长文版本。