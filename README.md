# loam — 不是“写人设”，不是“滚雪球”记忆，而是“让角色从记忆长出自我”，不断生长。

A memory runtime where identity continuity comes from raw dialogue, growth dynamics, and auditable reconstruction.
一个记忆运行时：身份连续性来自原始对话、生长动力学与可审计重建，而不是提示词拼装的人设脚本。

---

## What loam does

loam stores every conversational turn as immutable raw material, then digests that material into narrative memory, trait structure, and retrieval context. The runtime is designed for long-horizon character continuity: you can trace why a trait changed, inspect which evidence supported that shift, and rebuild derived layers when your model, policy, or prompts evolve. This design avoids recursive summary drift and gives you a stable identity substrate for months of interaction.

loam 会把每轮对话保存为不可变原料，再将其消化为叙事记忆、特质结构和检索上下文。它面向长期身份连续性：你可以追踪某个特质为何变化、查看其证据来源，并在模型、规则或提示词变化后重建派生层。这种设计避免“总结套总结”的递归漂移，为数月级交互提供稳定的身份底座。

---

## Why it is different

loam uses a no-snowball invariant: meaningful updates must anchor to raw turns, not to old persona summaries. Trait updates follow gated growth dynamics, where evidence accumulates first and commits later, so change is progressive rather than jittery. The runtime also separates chat-response model from growth/digest model, so you can tune latency and cognition independently instead of binding everything to one vendor and one model profile.

loam 采用“非滚雪球不变量”：关键更新必须锚定原始轮次，而不是旧人格总结。特质更新采用门控生长机制，证据先累积后提交，因此变化是渐进的，不会抖动跳变。同时它把聊天回复模型与生长/消化模型解耦，你可以分别优化延迟与认知质量，而不是被单一厂商和单一模型参数绑死。

---

## Growth formula and design logic

The growth system is driven by three linked terms: `capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`, `delta = plasticity * capacity * signal * salience`, and `gate = max(gate_floor, gate_ratio * capacity)`. In plain words, a trait does not jump immediately after one event; evidence is first accumulated in pending state and only committed after crossing the gate threshold. This is how loam keeps growth progressive, reduces random spikes, and still allows long-term qualitative shifts.

生长系统由三项联动公式驱动：`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`、`delta = plasticity * capacity * signal * salience`、`gate = max(gate_floor, gate_ratio * capacity)`。直白来说，特质不会因为一次事件立刻大跳，而是先在 pending 中累积证据，跨过门槛再提交变化。这就是 loam 能同时做到“渐进变化、抑制乱跳、长期可质变”的原因。

The design thought process is: preserve immutable raw turns as ground truth, let derived layers remain rebuildable, then use gated dynamics to convert repeated evidence into stable identity structure. This is not a one-shot personality injection; it is a controlled emergence process with audit trails.

设计思路是：先把不可变原始轮次作为真值底座，再让派生层保持可重建，最后用门控动力学把重复证据转化为稳定身份结构。这不是“一次性注入人设”，而是带审计轨迹的可控涌现过程。

---

## Deployment modes (not only Termux)

loam is not limited to Termux. You can run it in four mainstream ways: **Termux on Android** for personal always-on usage; **Linux server or VM** for stable long-running instances; **WSL/macOS local dev** for desktop development and debugging; and **containerized deployment** for reproducible team environments. All modes share the same core flow (`/context -> upstream -> /ingest`) and the same upstream mapping strategy. Detailed commands are in `DEPLOYMENT_MODES.md`.

loam 并不只支持 Termux。你可以用四种主流方式部署：**Android Termux**（个人常驻）、**Linux 服务器/虚拟机**（长期稳定运行）、**WSL/macOS 本地开发**（桌面调试）、**容器化部署**（团队可复现环境）。这些模式都共享同一套核心流程（`/context -> upstream -> /ingest`）和上游映射策略。详细命令见 `DEPLOYMENT_MODES.md`。

For full deployment guidance, read `FINAL_RELEASE.md` for one-stop playbook, `DEPLOYMENT_MODES.md` for cross-environment comparison, and `TERMUX_QUICKSTART.md` / `MULTI_UPSTREAM_QUICKSTART.md` for concrete startup commands.

如果要完整部署，请优先读 `FINAL_RELEASE.md`（一站式部署手册）、`DEPLOYMENT_MODES.md`（跨环境对比），以及 `TERMUX_QUICKSTART.md` / `MULTI_UPSTREAM_QUICKSTART.md`（可直接执行的启动命令）。

---

## Quick file map

Use `FINAL_RELEASE.md` for full deployment playbook and mode comparison, `TERMUX_QUICKSTART.md` for phone-first setup, `MULTI_UPSTREAM_QUICKSTART.md` for provider routing and model naming rules, `THIRD_PARTY_INTEGRATION.md` for MCP/plugin integration patterns, and `INTEGRATION_CHECKLIST.md` for pre-release verification. If you only read one technical file before launch, read `FINAL_RELEASE.md` first.

请按以下路径阅读：`FINAL_RELEASE.md`（完整部署与模式对比）、`TERMUX_QUICKSTART.md`（手机优先安装）、`MULTI_UPSTREAM_QUICKSTART.md`（多上游路由与模型命名）、`THIRD_PARTY_INTEGRATION.md`（MCP/插件接入模式）、`INTEGRATION_CHECKLIST.md`（发布前校验）。如果上线前只看一份技术文档，优先看 `FINAL_RELEASE.md`。

---

## Highlight visual-content module (normal page)

Use a four-block visual narrative on the normal project page: **Block A: problem framing** (why summary-recursion drifts), **Block B: pipeline architecture** (`/context -> upstream -> /ingest`), **Block C: growth mechanics** (capacity/delta/gate with pending accumulation), and **Block D: deployment matrix** (Termux/Linux/WSL-Desktop/Container). Each block should include one screenshot or diagram and one paragraph explaining the operational implication, so visitors can understand both concept and execution path within one screen scroll.

建议在常规项目页使用四段式图文结构：**A 段：问题定义**（为什么总结递归会漂移）、**B 段：流程架构**（`/context -> upstream -> /ingest`）、**C 段：生长机制**（capacity/delta/gate 与 pending 累积）、**D 段：部署矩阵**（Termux/Linux/WSL-桌面/容器）。每段配置一张图和一段“运维含义说明”，让访问者在一屏滚动内同时理解理念与落地路径。

---

## Security boundary

By default, provider keys are read from your own local files or environment variables and used by your own runtime process to call your selected upstream providers. loam does not require uploading your provider keys to maintainers, and normal operation does not depend on a maintainer-controlled mandatory cloud relay. You still need to protect your host, plugins, and secret files under your own trust model.

默认情况下，上游 key 从你自己的本地文件或环境变量读取，由你本地运行进程发往你选择的上游提供方。loam 不要求把上游 key 上传给维护者，常规运行也不依赖维护者托管的强制云端中继。你仍需在自己的信任模型下保护主机环境、插件和密钥文件。

---

Don’t hard-freeze a persona. Grow a self from memory.
别写太固化的人设，让“自我”从记忆中生长。