# loam Third-Party Integration (MCP / Plugin / Script Bridge)

loam is an independent HTTP memory runtime, not a model-specific plugin.
loam 是独立的 HTTP 记忆运行时，不是绑定某个模型的插件。

It binds to character identity continuity, not to a single LLM vendor.
它绑定的是角色身份连续性，而不是某一家 LLM 供应商。

---

## One-line positioning
## 一句话定位

Keep memory in loam, keep models replaceable.
把记忆放在 loam，把模型保持可替换。

---

## Recommended integration options
## 推荐接入方式

### Option A: MCP adapter
### 方案 A：MCP 适配层

Map MCP tools to loam HTTP endpoints.
把 MCP 工具映射到 loam HTTP 端点。

`loam_context(query, learn=true)` -> `POST /context`.
`loam_context(query, learn=true)` -> `POST /context`。

`loam_ingest(session, turns[])` -> `POST /ingest`.
`loam_ingest(session, turns[])` -> `POST /ingest`。

`loam_digest(limit?)` -> `POST /digest` (optional if background grower runs).
`loam_digest(limit?)` -> `POST /digest`（若后台 grower 在跑则可选）。

### Option B: Platform hooks / plugin callbacks
### 方案 B：平台钩子 / 插件回调

Before generation, call `/context` and inject returned text into prompt context.
生成前调用 `/context`，把返回文本注入提示上下文。

After generation, write user+assistant raw turns into `/ingest`.
生成后把 user+assistant 原文轮次写入 `/ingest`。

### Option C: Forced proxy bridge (recommended)
### 方案 C：强制代理桥（推荐）

Use a local OpenAI-compatible proxy that enforces the full sequence.
使用本地 OpenAI 兼容代理，强制执行完整流程。

`/context -> upstream model -> /ingest` on every turn.
每轮固定执行 `/context -> 上游模型 -> /ingest`。

This avoids memory loss caused by uncertain tool-calling behavior.
这能避免因工具调用不稳定造成的记忆漏写。

---

## Raw text vs summary upload
## 传原文还是传总结

Recommended default is raw-turn upload for every round.
默认推荐每轮上传原文轮次。

Summary extraction happens inside loam digest stage, not before ingest.
总结抽取发生在 loam 的 digest 阶段，而不是 ingest 之前。

So missing summary calls will not drop raw memory.
所以即使没有总结调用，也不会丢原始记忆。

---

## Minimal HTTP examples
## 最小 HTTP 示例

Fetch context:
获取上下文：

```bash
curl -s -X POST http://127.0.0.1:8765/context \
  -H 'Content-Type: application/json' \
  -d '{"query":"I am nervous about tomorrow\'s meeting","learn":true}'
```

```bash
curl -s -X POST http://127.0.0.1:8765/context \
  -H 'Content-Type: application/json' \
  -d '{"query":"我对明天开会有点紧张","learn":true}'
```

Ingest one round:
入库一轮对话：

```bash
curl -s -X POST http://127.0.0.1:8765/ingest \
  -H 'Content-Type: application/json' \
  -d '{"session":"chat-001","turns":[{"turn":120,"role":"user","content":"I am nervous"},{"turn":120,"role":"assistant","content":"Let us split preparation steps"}]}'
```

```bash
curl -s -X POST http://127.0.0.1:8765/ingest \
  -H 'Content-Type: application/json' \
  -d '{"session":"chat-001","turns":[{"turn":120,"role":"user","content":"我有点紧张"},{"turn":120,"role":"assistant","content":"我们把准备步骤拆开"}]}'
```

---

## Security statement for URL/API concerns
## 面向 URL/API 顾虑的安全声明

Agent points to your local proxy URL, not to a maintainer-owned server.
Agent 指向的是你的本地代理 URL，而不是维护者托管服务器。

Keys are loaded from your local env/files and sent only to your chosen upstream endpoints.
key 从你的本地环境/文件加载，只会发往你选择的上游端点。

loam does not require transmitting your provider keys to project maintainers.
loam 不要求把你的上游 key 传给项目维护者。

Security still depends on your host hardening and provider trust model.
安全性仍然取决于你的主机防护与上游提供方可信模型。