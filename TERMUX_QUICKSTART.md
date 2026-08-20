# loam Termux Quickstart (Android)

This guide is for users who deploy loam on a single Android device with Termux.
本指南面向在单台 Android 设备上使用 Termux 部署 loam 的用户。

> If you need ultra-detailed step-by-step guidance (beginner friendly), read:
> `docs/DEPLOYMENT_FOR_ABSOLUTE_BEGINNERS.md`
>
> 如果你希望看到“每一步都拆开讲”的零基础手册，请看：
> `docs/DEPLOYMENT_FOR_ABSOLUTE_BEGINNERS.md`

---

## Before you start

You need Termux, internet access, and one upstream provider account with API URL/key/model. All commands below run inside Termux terminal, not in chat input boxes or browser pages.

你需要准备 Termux、可联网环境，以及至少一个上游提供方的 API URL/key/model。下面所有命令都在 Termux 终端执行，不是在聊天输入框或浏览器页面执行。

---

## Install dependencies and clone repository

Install Python, Git, and curl first, then clone repository into home directory. If repository already exists, enter the folder and run `git pull`.

先安装 Python、Git、curl，再把仓库拉到 home 目录。如果仓库已存在，进入目录后执行 `git pull` 更新。

```bash
pkg update -y
pkg install -y python git curl
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

---

## Prepare upstream mapping

The "upstream template" in this guide means the sample file inside this repository: `~/loam/bridge/upstreams.example.json`. It is only a starter template with placeholder values (`sk-xxx`, `example.com`). You must copy it to `~/.loam/upstreams.json` and replace placeholders with your real provider settings.

本指南里的“上游模板”指仓库内示例文件：`~/loam/bridge/upstreams.example.json`。它只是带占位值（`sk-xxx`、`example.com`）的样板，不能直接用于生产。你需要复制成 `~/.loam/upstreams.json`，再改成真实参数。

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK
```

---

## Start loam + proxy in one command

This startup command initializes the full path used by clients. It launches loam service, launches forced proxy, and runs health checks. `LOAM_API_KEY` is for loam internal digest/growth calls rather than direct client chat requests.

该命令会初始化客户端使用的完整链路：先启动 loam，再启动强制代理，并做健康检查。`LOAM_API_KEY` 用于 loam 内部消化/生长调用，不是客户端直接聊天调用的 key。

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

---

## Configure client fields

Set client Base URL to `http://127.0.0.1:8780/v1`, set model to `provider/model` (for example `relayA/gpt-4o-mini`), and if your client requires non-empty API key for local endpoint, use any placeholder string.

客户端 Base URL 填 `http://127.0.0.1:8780/v1`，模型填 `provider/model`（如 `relayA/gpt-4o-mini`），如果客户端要求本地端点 API key 非空，可填写任意占位字符串。

---

## Verify health and daily operations

After startup, verify `/health` and `/v1/models` endpoints. For daily operations, use status/stop/start scripts and keep logs for troubleshooting.

启动后请验证 `/health` 与 `/v1/models`。日常运维请使用 status/stop/start 脚本，并保留日志用于排错。

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
bash scripts/termux/final_stop_all.sh
```

---

## Security boundary

Upstream credentials stay in your local runtime files/environment by default and are used by your local process to call selected providers. loam does not require sending provider credentials to maintainers.

默认情况下，上游凭证保存在你本地运行环境的文件/环境变量中，由本地进程发往你选择的提供方。loam 不要求把上游凭证发送给维护者。