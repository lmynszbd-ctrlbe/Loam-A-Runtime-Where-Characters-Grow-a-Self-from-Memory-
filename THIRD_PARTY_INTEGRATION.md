# loam Third-Party Integration Guide

This guide describes how to connect loam with MCP adapters, plugin hooks, and script bridges without losing memory reliability.
本指南说明如何把 loam 接入 MCP 适配层、插件钩子和脚本桥接，同时保持记忆链路可靠。

---

## Integration principle

Keep memory in loam and keep model vendors replaceable. Third-party layers should call loam context before generation and write raw turns after generation. If your host platform has uncertain tool-calling behavior, put a forced proxy in front so every turn still executes the full memory pipeline.

核心原则是“记忆归 loam、模型可替换”。第三方层应在生成前调用 loam context，在生成后写入原始轮次。如果宿主平台工具调用不稳定，建议前置强制代理，确保每轮都执行完整记忆流水线。

---

## Option A: MCP adapter

Expose loam endpoints as MCP tools such as `loam_context`, `loam_ingest`, and optional `loam_digest`. This gives explicit contract boundaries and simplifies testing because each stage has observable request/response payloads.

可以把 loam 端点封装成 MCP 工具，例如 `loam_context`、`loam_ingest`、可选 `loam_digest`。这种方式的边界最清晰，便于测试，因为每个阶段都有可观察的请求/响应。

---

## Option B: Plugin hooks

If your platform supports pre-generation and post-generation hooks, call `/context` before model invocation and call `/ingest` after receiving assistant output. This mode is lightweight and works well when plugin lifecycle is stable.

如果平台支持生成前/生成后钩子，可在模型调用前请求 `/context`，在拿到回复后请求 `/ingest`。这种方式最轻量，适合插件生命周期稳定的平台。

---

## Option C: Forced proxy bridge (recommended)

Route all client traffic through local proxy and let proxy enforce `/context -> upstream -> /ingest` automatically. This removes dependence on host tool-call reliability and is the most robust path for production-like continuity.

把所有客户端请求先走本地代理，让代理自动强制执行 `/context -> upstream -> /ingest`。它不依赖宿主工具调用是否稳定，是更接近生产稳态的方案。

---

## Raw-turn vs summary upload

Upload raw turns as default. Summaries should be generated inside loam digest stage rather than upstream host layer. This preserves reconstruction ability and avoids information loss when external summarization quality fluctuates.

默认上传原始轮次，不要在宿主层先做摘要。摘要应由 loam 的 digest 阶段生成，这样可保留可重建能力，避免外部摘要质量波动导致的信息丢失。

---

## Minimal API examples

Use `/context` for retrieval and `/ingest` for writing one turn pair. Keep session ids stable across the same user/agent identity to maintain continuity.

使用 `/context` 做检索、`/ingest` 写入一轮 user+assistant。请保证同一身份链路下 session id 稳定，才能维持连续性。

```bash
curl -s -X POST http://127.0.0.1:8765/context -H 'Content-Type: application/json' -d '{"query":"I am nervous about tomorrow\'s meeting","learn":true}'
curl -s -X POST http://127.0.0.1:8765/ingest -H 'Content-Type: application/json' -d '{"session":"chat-001","turns":[{"turn":120,"role":"user","content":"I am nervous"},{"turn":120,"role":"assistant","content":"Let us split preparation steps"}]}'
```

---

## Security boundary

Client points to local proxy URL, local runtime reads provider credentials, and requests go directly to configured upstream providers. The project does not require forwarding provider keys to maintainers.

客户端连本地代理 URL，本地运行时读取 provider 凭证，请求直接发往你配置的上游提供方。项目不要求把 provider key 转发给维护者。