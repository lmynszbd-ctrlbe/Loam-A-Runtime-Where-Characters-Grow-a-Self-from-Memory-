# Multi-Upstream Quickstart (forced proxy)

This file answers one question: what does “upstream configured” actually mean?
本文件专门回答一个问题：到底什么叫“上游配好”。

---

## Concept
## 概念

Agent uses one local URL: `http://127.0.0.1:8780/v1`.
Agent 只使用一个本地 URL：`http://127.0.0.1:8780/v1`。

Proxy still needs a map of real upstream providers and keys.
代理仍需要知道真实上游提供方与对应 key。

That map is `~/.loam/upstreams.json`.
这个映射文件就是 `~/.loam/upstreams.json`。

---

## Create config from template
## 从模板创建配置

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

---

## Edit `~/.loam/upstreams.json`
## 编辑 `~/.loam/upstreams.json`

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

`default` is the fallback provider.
`default` 是默认回退 provider。

`providers.<name>.base_url` must be OpenAI-compatible upstream base URL.
`providers.<name>.base_url` 必须是 OpenAI 兼容上游基址。

---

## Start loam service
## 启动 loam 服务

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/start_loam.sh
```

```bash
cd ~/loam
LOAM_API_KEY='你的生长key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/start_loam.sh
```

---

## Start forced proxy
## 启动强制代理

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/start_forced_proxy.sh
```

```bash
cd ~/loam
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/start_forced_proxy.sh
```

---

## Agent settings
## Agent 设置

Base URL: `http://127.0.0.1:8780/v1`.
Base URL：`http://127.0.0.1:8780/v1`。

API key: any placeholder if client requires it.
API key：如果客户端强制要求，可填任意占位值。

Model format: `provider/model`.
模型格式：`provider/model`。

Example: `relayA/gpt-4o-mini`, `relayB/claude-3-5-sonnet`.
示例：`relayA/gpt-4o-mini`、`relayB/claude-3-5-sonnet`。

---

## Verify
## 验证

```bash
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

```bash
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

If `/v1/models` shows `provider/model`, mapping works.
如果 `/v1/models` 能看到 `provider/model`，映射已生效。

---

## Security note
## 安全说明

Upstream keys remain in your local config file unless you share that file yourself.
除非你自己分享配置文件，否则上游 key 始终留在本地配置中。

Proxy forwards requests from your runtime to your providers; not to project maintainers.
代理只把请求从你的运行环境转发到你的上游提供方，不会转发给项目维护者。