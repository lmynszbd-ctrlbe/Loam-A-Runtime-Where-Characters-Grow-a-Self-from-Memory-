# loam Final Start Guide (Termux, detailed)

This is the full startup and explanation guide for release usage.
这是面向发布使用场景的完整启动与原理说明文档。

If you are new to command line, follow sections in order and do not skip prerequisites.
如果你是命令行新手，请按顺序执行，不要跳过前置准备。

---

## A. What this stack contains
## A. 这套栈包含什么

`loam` service stores raw dialogue and runs memory digestion/growth logic.
`loam` 服务负责保存原始对话，并执行记忆消化/生长逻辑。

`forced proxy` provides OpenAI-compatible endpoint and enforces memory pipeline per turn.
`forced proxy` 提供 OpenAI 兼容入口，并在每轮强制执行记忆流水线。

End-to-end per turn flow is: `/context -> upstream model -> /ingest`.
每轮端到端流程是：`/context -> 上游模型 -> /ingest`。

---

## B. Where commands should run
## B. 命令应该在哪里运行

Run commands in Termux terminal after entering repository directory.
命令要在 Termux 终端中执行，并先进入仓库目录。

Do not run shell commands in chat input box or GitHub web pages.
不要在聊天输入框或 GitHub 网页里执行 shell 命令。

---

## C. Prerequisites (first-time setup)
## C. 前置条件（首次使用）

```bash
pkg update -y
pkg install -y python git curl
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

```bash
pkg update -y
pkg install -y python git curl
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

---

## D. What “upstream configured” means
## D. “配好上游”到底是什么意思

Your Agent only points to local proxy URL, but proxy must know real provider mapping.
你的 Agent 只指向本地代理 URL，但代理必须知道真实上游映射关系。

That mapping is stored in `~/.loam/upstreams.json`.
这个映射文件就是 `~/.loam/upstreams.json`。

Create from template:
从模板创建：

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

Fill real values for `base_url`, `api_key`, and `default_model`.
把 `base_url`、`api_key`、`default_model` 改成真实值。

---

## E. One-command final startup (multi-upstream)
## E. 一条命令最终启动（多上游）

```bash
cd ~/loam
LOAM_API_KEY='your_loam_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

```bash
cd ~/loam
LOAM_API_KEY='你的loam生长key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

This command starts loam, starts proxy, and performs health checks automatically.
该命令会自动启动 loam、启动代理并完成健康检查。

---

## F. URL/API explanation (what to fill and why)
## F. URL/API 解释（填什么、为什么填）

`LOAM_API_KEY`: credential for loam internal digest/growth model calls.
`LOAM_API_KEY`：loam 内部消化/生长模型调用凭证。

`LOAM_MODEL`: model id used by loam for reflection/digest stage.
`LOAM_MODEL`：loam 在反思/消化阶段使用的模型 id。

`UPSTREAM base_url/api_key/model`: routing target used by forced proxy for chat completion.
`UPSTREAM base_url/api_key/model`：强制代理发起聊天补全时使用的路由目标。

Agent `Base URL` should be local proxy endpoint `http://127.0.0.1:8780/v1`.
Agent 的 `Base URL` 应填本地代理入口 `http://127.0.0.1:8780/v1`。

Agent `API key` can be any placeholder if client requires non-empty value.
如果客户端要求 API key 非空，Agent 的 `API key` 可填任意占位值。

Agent `Model` in multi-upstream mode must be `provider/model`.
多上游模式下 Agent 的 `Model` 必须是 `provider/model` 形式。

---

## G. Agent-side final settings
## G. Agent 侧最终填写示例

Base URL: `http://127.0.0.1:8780/v1`
Base URL：`http://127.0.0.1:8780/v1`

API key: `local-placeholder` (or any non-empty placeholder)
API key：`local-placeholder`（或任意非空占位值）

Model example 1: `relayA/gpt-4o-mini`
Model 示例 1：`relayA/gpt-4o-mini`

Model example 2: `relayB/claude-3-5-sonnet`
Model 示例 2：`relayB/claude-3-5-sonnet`

---

## H. Verification commands
## H. 验证命令

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

If all interfaces return JSON and models list is present, startup is complete.
如果接口都返回 JSON 且模型列表可见，说明启动完成。

---

## I. Security statement for URL/API concerns
## I. 面向 URL/API 顾虑的安全说明

By default, provider keys are read from your local env/files on your own device.
默认情况下，上游 key 从你设备本地环境变量/配置文件读取。

Requests are sent from your local process to your selected upstream providers.
请求由你的本地进程发往你自己选择的上游提供方。

The project does not require sending your upstream keys to maintainers.
项目不要求把上游 key 发送给维护者。

Normal runtime does not depend on project-owned mandatory cloud endpoints.
常规运行不依赖项目方托管的强制云端端点。

---

## J. Daily operations
## J. 日常运维

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
bash scripts/termux/final_start_all.sh
bash scripts/termux/log_loam.sh
```

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
bash scripts/termux/final_start_all.sh
bash scripts/termux/log_loam.sh
```

---

## K. Typical failure points
## K. 常见失败点

`LOAM_API_KEY` or `LOAM_MODEL` missing when startup script runs.
启动时缺失 `LOAM_API_KEY` 或 `LOAM_MODEL`。

Upstream `base_url` or `api_key` invalid in `~/.loam/upstreams.json`.
`~/.loam/upstreams.json` 里的上游 `base_url` 或 `api_key` 无效。

Model name not in `provider/model` format under multi-upstream mode.
多上游模式下模型名未使用 `provider/model` 格式。

---

Persistent memory should be reliable before it is elegant.
记忆系统首先要“可靠可复现”，然后才谈“优雅表达”。