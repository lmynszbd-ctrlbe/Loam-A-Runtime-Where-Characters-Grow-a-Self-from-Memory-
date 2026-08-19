# loam Final Start Guide (Termux)

This file explains the final startup path with security notes.
本文件说明最终启动路径，并补充安全说明。

---

## What “upstream configured” means
## “配好上游”是什么意思

Your Agent points to one local proxy URL, but the proxy needs routing targets.
你的 Agent 只指向一个本地代理 URL，但代理仍需要知道要转发到哪里。

Those routing targets are defined in `~/.loam/upstreams.json`.
这些转发目标定义在 `~/.loam/upstreams.json`。

Copy template first:
先复制模板：

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
```

Then fill your real `base_url`, `api_key`, and `default_model`.
然后填入真实的 `base_url`、`api_key` 和 `default_model`。

---

## One command (multi-upstream)
## 一条命令（多上游）

```bash
cd ~/loam && \
LOAM_API_KEY='your_loam_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam生长key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

Startup order is orchestrated automatically.
脚本会自动完成启动顺序编排。

loam service -> forced proxy -> health checks (`/health`, `/v1/models`).
loam 服务 -> 强制代理 -> 健康检查（`/health`、`/v1/models`）。

---

## One command (single upstream)
## 一条命令（单上游）

```bash
cd ~/loam && \
LOAM_API_KEY='your_loam_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAM_BASE_URL='https://your-relay.example.com' \
UPSTREAM_API_KEY='your_upstream_key' \
UPSTREAM_MODEL='your_default_model' \
bash scripts/termux/final_start_all.sh
```

```bash
cd ~/loam && \
LOAM_API_KEY='你的loam生长key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAM_BASE_URL='你的中转地址' \
UPSTREAM_API_KEY='你的中转key' \
UPSTREAM_MODEL='你的默认模型' \
bash scripts/termux/final_start_all.sh
```

---

## What to fill in Agent
## Agent 里怎么填写

Base URL: `http://127.0.0.1:8780/v1`.
Base URL：`http://127.0.0.1:8780/v1`。

API key can be any placeholder if your client requires one.
如果客户端强制要求 API key，可填任意占位值。

Model format is `provider/model` in multi-upstream mode.
多上游模式下模型格式为 `provider/model`。

---

## Security note (important)
## 安全说明（重要）

API keys stay in your local runtime files/env and are used by your local process.
API key 保留在你本地运行环境的文件/环境变量中，由本地进程使用。

Keys are sent to your selected upstream providers, not to project maintainers.
key 会发往你选择的上游提供方，不会发给项目维护者。

No project-owned mandatory cloud endpoint is required for normal operation.
正常运行不依赖项目方托管的强制云端端点。

---

## Management commands
## 管理命令

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
```

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
bash scripts/termux/final_stop_all.sh
```