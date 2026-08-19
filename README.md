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

## Deployment modes (not only Termux)

loam is not limited to Termux. You can run it in four mainstream ways: **Termux on Android** for personal always-on usage; **Linux server or VM** for stable long-running instances; **WSL/macOS local dev** for desktop development and debugging; and **containerized deployment** for reproducible team environments. All modes share the same core flow (`/context -> upstream -> /ingest`) and the same upstream mapping strategy. Detailed commands are in `DEPLOYMENT_MODES.md`.

loam 并不只支持 Termux。你可以用四种主流方式部署：**Android Termux**（个人常驻）、**Linux 服务器/虚拟机**（长期稳定运行）、**WSL/macOS 本地开发**（桌面调试）、**容器化部署**（团队可复现环境）。这些模式都共享同一套核心流程（`/context -> upstream -> /ingest`）和上游映射策略。详细命令见 `DEPLOYMENT_MODES.md`。

---

## Quick file map

Use `FINAL_RELEASE.md` for full deployment playbook and mode comparison, `TERMUX_QUICKSTART.md` for phone-first setup, `MULTI_UPSTREAM_QUICKSTART.md` for provider routing and model naming rules, `THIRD_PARTY_INTEGRATION.md` for MCP/plugin integration patterns, and `INTEGRATION_CHECKLIST.md` for pre-release verification. If you only read one technical file before launch, read `FINAL_RELEASE.md` first.

请按以下路径阅读：`FINAL_RELEASE.md`（完整部署与模式对比）、`TERMUX_QUICKSTART.md`（手机优先安装）、`MULTI_UPSTREAM_QUICKSTART.md`（多上游路由与模型命名）、`THIRD_PARTY_INTEGRATION.md`（MCP/插件接入模式）、`INTEGRATION_CHECKLIST.md`（发布前校验）。如果上线前只看一份技术文档，优先看 `FINAL_RELEASE.md`。

---

## Security boundary

By default, provider keys are read from your own local files or environment variables and used by your own runtime process to call your selected upstream providers. loam does not require uploading your provider keys to maintainers, and normal operation does not depend on a maintainer-controlled mandatory cloud relay. You still need to protect your host, plugins, and secret files under your own trust model.

默认情况下，上游 key 从你自己的本地文件或环境变量读取，由你本地运行进程发往你选择的上游提供方。loam 不要求把上游 key 上传给维护者，常规运行也不依赖维护者托管的强制云端中继。你仍需在自己的信任模型下保护主机环境、插件和密钥文件。

---

Don’t script a persona. Grow a self from memory.
别写人设，让“自我”从记忆中生长。