# Multi-Upstream Quickstart (forced proxy)

This guide explains what “upstream configured” means, why it matters, and how to verify routing.
本指南解释“配好上游”的含义、必要性与验证方式。

---

## What upstream mapping does

Your client sees one local OpenAI-compatible URL, but proxy still needs real destinations for each provider. Upstream mapping defines those destinations and credentials, and lets a single local endpoint route to multiple model vendors with explicit `provider/model` naming.

客户端只看到一个本地 OpenAI 兼容入口，但代理仍需要知道每个 provider 的真实目标地址与凭证。上游映射就是这份“路由字典”，它让单一本地端点通过 `provider/model` 命名路由到多个模型供应商。

---

## Create and edit mapping file

Create `~/.loam/upstreams.json` from template, then replace placeholder fields with real values. Keep JSON syntax intact (commas, braces, quotes), because malformed JSON will prevent proxy startup.

从模板创建 `~/.loam/upstreams.json` 后，把占位值替换为真实参数。请保持 JSON 语法完整（逗号、花括号、引号），否则代理无法启动。

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

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

---

## Start services and route traffic

Start loam first, then start forced proxy with your mapping file. The proxy reads requested model, resolves provider prefix, and forwards requests to mapped upstream URL with corresponding key.

先启动 loam，再通过映射文件启动强制代理。代理会读取请求模型名，解析 provider 前缀，并用对应 key 转发到映射中的上游 URL。

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/start_loam.sh
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" UPSTREAM_DEFAULT='relayA' bash scripts/termux/start_forced_proxy.sh
```

---

## Client-side model naming rules

Use Base URL `http://127.0.0.1:8780/v1` and model format `provider/model`. If model has no provider prefix, proxy falls back to `default` provider from upstream config. This makes failover and vendor switching explicit and predictable.

客户端 Base URL 使用 `http://127.0.0.1:8780/v1`，模型名使用 `provider/model`。如果模型名没有 provider 前缀，代理会回退到 upstream 配置中的 `default`。这样切换供应商和故障回退都更明确、可预期。

---

## Verification and troubleshooting

A valid setup returns provider-prefixed models from `/v1/models` and healthy JSON from `/health`. Empty models usually indicate wrong upstream credentials or an incompatible upstream endpoint. Startup failures should be diagnosed from `~/.loam/run/forced_proxy.log` first.

正确配置后，`/v1/models` 会返回带 provider 前缀的模型，`/health` 返回健康 JSON。模型列表为空通常意味着上游凭证错误或端点不兼容。启动失败优先查看 `~/.loam/run/forced_proxy.log`。

```bash
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

---

## Security boundary

Provider keys remain in local config unless you export or share that file. Proxy forwards requests to providers you selected and does not require sending keys to maintainers.

除非你主动导出或分享配置文件，上游 key 会保留在本地。代理仅转发到你选定的 provider，不要求把 key 发送给维护者。