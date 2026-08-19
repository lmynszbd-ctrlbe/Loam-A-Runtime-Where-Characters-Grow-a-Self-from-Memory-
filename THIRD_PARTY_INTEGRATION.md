# loam 第三方接入说明（MCP / 插件 / 自定义脚本）

## 一句话定位

**loam 本体是“独立 HTTP 记忆进程”**，不是某个特定聊天模型插件。  
它绑定的是 `character`（角色），不是绑定某个模型。

- 你换模型：角色记忆还在。
- 你换客户端：角色记忆还在。
- 你迁移设备：拷走数据目录即可。

---

## 推荐接入方式

### 方案 A（优先）：MCP 工具适配层

如果三方软件支持 MCP，就做 3 个工具映射到 loam HTTP：

1. `loam_context(query, learn=true)` -> `POST /context`
2. `loam_ingest(session, turns[])` -> `POST /ingest`
3. `loam_digest(limit?)` -> `POST /digest`（或后台自己跑）

可选：
- `loam_stats()` -> `GET /stats`
- `loam_health()` -> `GET /health`

> 这样任何 MCP 客户端都能复用 loam，而不被某个平台绑定。

---

### 方案 B：平台插件 / Webhook（不支持 MCP）

很多平台有“发送前/发送后钩子”：

- 发送给模型前：调用 `/context`，把 `text` 拼到系统提示词
- 模型回复后：把 user+assistant 双边落 `/ingest`
- 空闲时：调用 `/digest`（或依赖 loam 后台 grower）

---

### 方案 C：最小脚本桥（推荐：强制流程代理）

如果平台连插件都没有，就用一个本地代理接管 OpenAI 兼容入口。
代理里串上 loam 的 3 步：

1) `context = /context`
2) 调上游模型 API
3) `/ingest` +（可选）`/digest`

并且可以做**多上游聚合**（你有多个不同中转时最实用）：
- 代理的 `/v1/models` 聚合所有上游模型
- 模型名形如 `provider/model`（例如 `relayA/gpt-4o-mini`、`relayB/claude-3-5-sonnet`）
- 你在 agent 里直接切换不同家的模型即可

---

## 你刚问的关键：传原文还是传总结？

**默认推荐：每一轮都传原文（user + assistant）到 loam。**

- 传的是原始轮次文本，不是先总结再传。
- 总结/抽事件发生在 loam 内部 digest 阶段（后台），原文 L0 永久保留。
- 这样就不会出现“平台没总结到就丢记忆”的问题。

## 对话时序（关键）

每轮对话建议这样走：

1. 用户输入到来：
   - 调 loam `/context`（query=用户本轮文本）
   - 将返回 `text` 注入系统上下文
2. 调外部模型生成回复
3. 立即把本轮 user+assistant 落到 loam `/ingest`
4. 让 loam 后台 grower 自动消化（或手动 `/digest`）

---

## 最小 HTTP 示例

### 1) 取上下文

```bash
curl -s -X POST http://127.0.0.1:8765/context \
  -H 'Content-Type: application/json' \
  -d '{"query":"我明天开会有点紧张","learn":true}'
```

### 2) 记录本轮对话

```bash
curl -s -X POST http://127.0.0.1:8765/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "session":"chat-001",
    "turns":[
      {"turn": 120, "role":"user", "content":"我明天开会有点紧张"},
      {"turn": 120, "role":"assistant", "content":"我们先把准备步骤拆开"}
    ]
  }'
```

### 3) 手动消化（可选）

```bash
curl -s -X POST http://127.0.0.1:8765/digest -H 'Content-Type: application/json' -d '{}'
```

---

## 什么时候必须 API key

- 你要“持续自生长”（抽事件/判特质/自述/漂移审计）=> **必须 key**
- 你只想“先当记忆缓存/上下文插件” => 理论可不跑 grower，但你当前配置已切到“必须 key 启动”模式

---

## 结论

- **形态上**：loam 是独立进程 + HTTP 能力层。
- **生态接入上**：优先 MCP；不支持 MCP 就插件/脚本桥。
- **核心原则上**：永远是“角色记忆中心”，不是“模型私有记忆”。