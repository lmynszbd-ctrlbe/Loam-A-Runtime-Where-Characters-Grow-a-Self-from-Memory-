# Multi-Upstream Quickstart (forced proxy)

This guide explains exactly what “configure upstreams” means and how to do it safely.
这份指南专门解释“配好上游”到底是什么意思，以及如何安全完成配置。

All commands run in Termux terminal under your local environment.
所有命令都在你本地 Termux 终端中执行。

---

## 1) Why upstream config exists
## 1）为什么需要上游配置

Your Agent only sees one local endpoint (`127.0.0.1`), but proxy still needs real provider targets.
你的 Agent 只看到一个本地入口（`127.0.0.1`），但代理仍然需要真实上游目标。

Upstream config tells proxy which provider URL, key, and model to use.
上游配置就是告诉代理：该用哪个提供方 URL、哪个 key、哪个默认模型。

Without this config, proxy cannot route chat requests to real model services.
没有这份配置，代理无法把聊天请求路由到真实模型服务。

---

## 2) Create config file from template
## 2）从模板创建配置文件

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

If `nano` is unfamiliar, edit line by line and do not remove commas or braces.
如果你不熟悉 `nano`，请逐行修改，不要删掉逗号和花括号。

---

## 3) Fill JSON fields (what each field means)
## 3）填写 JSON 字段（每个字段是什么）

Example:
示例：

```json
{
  "default": "relayA",
  "providers": {
    "relayA": {
      "base_url": "https://relay-a.example.com",
      "api_key": "sk-xxxx",
      "default_model": "gpt-4o-mini"
    },
    "relayB": {
      "base_url": "https://relay-b.example.com",
      "api_key": "sk-yyyy",
      "default_model": "claude-3-5-sonnet"
    }
  }
}
```

`default` is fallback provider name when request does not specify provider explicitly.
`default` 是默认 provider 名称，当请求没显式指定 provider 时使用它。

`providers.<name>.base_url` is your upstream OpenAI-compatible API base URL.
`providers.<name>.base_url` 是你的上游 OpenAI 兼容 API 基址。

`providers.<name>.api_key` is your upstream provider key.
`providers.<name>.api_key` 是对应上游提供方的 key。

`providers.<name>.default_model` is fallback model for that provider.
`providers.<name>.default_model` 是该 provider 的默认模型。

---

## 4) Start loam first
## 4）先启动 loam

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/start_loam.sh
```

`LOAM_API_KEY` and `LOAM_MODEL` are for loam internal growth/digest model.
`LOAM_API_KEY` 和 `LOAM_MODEL` 用于 loam 内部生长/消化模型。

---

## 5) Start forced proxy with upstream map
## 5）再用上游映射启动强制代理

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/start_forced_proxy.sh
```

Proxy exposes OpenAI-compatible endpoint locally at `http://127.0.0.1:8780/v1`.
代理会在本地暴露 OpenAI 兼容入口：`http://127.0.0.1:8780/v1`。

---

## 6) Agent-side settings
## 6）Agent 侧填写方式

Base URL: `http://127.0.0.1:8780/v1`
Base URL：`http://127.0.0.1:8780/v1`

API key: placeholder if your client requires non-empty input.
API key：如客户端要求非空，可填任意占位值。

Model format: `provider/model`.
模型格式：`provider/model`。

Examples: `relayA/gpt-4o-mini`, `relayB/claude-3-5-sonnet`.
示例：`relayA/gpt-4o-mini`、`relayB/claude-3-5-sonnet`。

---

## 7) How routing works (principle)
## 7）路由原理（为什么这样填）

Agent sends request to local proxy instead of remote provider directly.
Agent 不直接请求远程提供方，而是先请求本地代理。

Proxy reads `model` like `relayA/gpt-4o-mini`, selects `relayA` config, and forwards request.
代理读取 `relayA/gpt-4o-mini` 这样的模型名，先定位 `relayA` 配置，再转发请求。

During the same turn, proxy enforces `/context -> upstream -> /ingest` pipeline.
同一轮内，代理会强制执行 `/context -> upstream -> /ingest` 流程。

This is why memory write is reliable even if tool-calling is unstable.
这就是即使工具调用不稳定，记忆写入仍然可靠的原因。

---

## 8) Verify and troubleshoot
## 8）验证与排错

```bash
cd ~/loam
bash scripts/termux/status_loam.sh
bash scripts/termux/status_forced_proxy.sh
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

If `/v1/models` is empty, your upstream URL/key is likely invalid.
如果 `/v1/models` 为空，通常是上游 URL/key 不正确。

If proxy fails to start, inspect log file at `~/.loam/run/forced_proxy.log`.
如果代理启动失败，请查看日志 `~/.loam/run/forced_proxy.log`。

---

## 9) Security note
## 9）安全说明

Your upstream keys stay in local config files unless you export/share them yourself.
除非你主动导出或分享，否则上游 key 会保留在本地配置文件中。

Proxy forwards to your chosen providers and does not upload keys to project maintainers.
代理只会转发到你选定的提供方，不会把 key 上传给项目维护者。

Never commit `~/.loam/upstreams.json` or screenshots with visible keys.
不要把 `~/.loam/upstreams.json` 或含明文 key 的截图提交到仓库。