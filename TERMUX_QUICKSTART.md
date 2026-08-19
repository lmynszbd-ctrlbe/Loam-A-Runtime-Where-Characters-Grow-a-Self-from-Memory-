# loam on Termux (Beginner-Friendly Quickstart)

This guide is written for first-time users who are not familiar with command-line workflows.
这份指南面向第一次接触命令行的小白用户，按步骤执行即可。

Every command in this file is executed in the Termux terminal window.
本文件中的所有命令都在 Termux 终端窗口执行。

---

## 0) What you need before running commands
## 0）开始前你需要准备什么

You need an Android phone, Termux app, and internet access.
你需要一台 Android 手机、Termux 应用和可联网环境。

You also need at least one upstream model provider account (for API URL + API key).
你还需要至少一个上游模型提供方账号（用于 API URL + API key）。

If you do not have upstream API credentials yet, prepare them first.
如果你还没有上游 API 凭证，请先准备好。

---

## 1) Install base packages in Termux
## 1）在 Termux 安装基础依赖

Open Termux, then run:
打开 Termux 后执行：

```bash
pkg update -y
pkg install -y python git curl
```

This installs Python runtime, Git (for clone/pull), and curl (for health checks).
这会安装 Python 运行时、Git（下载/更新代码）和 curl（健康检查）。

---

## 2) Download project code
## 2）下载项目代码

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

If `~/loam` already exists, you can update with `git pull` instead of cloning again.
如果 `~/loam` 已存在，可在目录内用 `git pull` 更新，而不是重复 clone。

---

## 3) Understand what URL/API you are filling
## 3）先理解你要填的 URL/API 是什么

`LOAM_API_KEY` is used by loam itself for memory digest/growth model calls.
`LOAM_API_KEY` 是 loam 内部做记忆消化/生长时调用模型的鉴权 key。

`UPSTREAM base_url/api_key/model` is used by forced proxy to call chat completion providers.
`UPSTREAM 的 base_url/api_key/model` 是强制代理调用聊天模型上游时用到的配置。

Agent `Base URL` points to local proxy (`127.0.0.1`) so every turn goes through forced memory flow.
Agent 的 `Base URL` 指向本地代理（`127.0.0.1`），保证每轮都经过强制记忆流程。

If your client asks for an API key on local endpoint, fill any placeholder.
如果客户端在本地端点也强制要 API key，填任意占位值即可。

---

## 4) Prepare upstream config file (recommended)
## 4）准备上游配置文件（推荐）

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

Replace `base_url`, `api_key`, and `default_model` with real values.
把 `base_url`、`api_key`、`default_model` 替换成真实值。

Save and exit nano with `Ctrl+O`, `Enter`, then `Ctrl+X`.
在 nano 中按 `Ctrl+O`、`Enter` 保存，再按 `Ctrl+X` 退出。

---

## 5) Start all services in one command
## 5）一条命令启动全部服务

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

This script starts loam first, then forced proxy, and then performs health checks.
这个脚本会先启动 loam，再启动强制代理，最后自动做健康检查。

---

## 6) Fill Agent settings
## 6）填写 Agent 设置

Base URL: `http://127.0.0.1:8780/v1`
Base URL：`http://127.0.0.1:8780/v1`

API key: any placeholder if required by your client.
API key：如果客户端强制要求可填任意占位值。

Model example: `relayA/gpt-4o-mini`.
Model 示例：`relayA/gpt-4o-mini`。

If you use another provider, replace `relayA` accordingly.
如果你使用其他 provider，请把 `relayA` 换成对应名称。

---

## 7) Verify startup result
## 7）验证启动结果

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

If all endpoints return JSON and models are listed, setup is successful.
如果接口都返回 JSON 且模型列表正常显示，说明配置成功。

---

## 8) Daily commands (start/stop/log)
## 8）日常命令（启动/停止/日志）

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

## 9) Common beginner mistakes
## 9）小白常见错误

Running commands in chat instead of Termux terminal.
把命令发在聊天框里，而不是在 Termux 终端里执行。

Forgetting to replace sample `api_key` in `~/.loam/upstreams.json`.
忘记把 `~/.loam/upstreams.json` 里的示例 `api_key` 换成真实值。

Using wrong model name format (must be `provider/model` in multi-upstream mode).
多上游模式使用了错误模型名格式（必须是 `provider/model`）。

Missing `LOAM_API_KEY` or `LOAM_MODEL` when running start script.
启动脚本时没提供 `LOAM_API_KEY` 或 `LOAM_MODEL`。

---

## 10) Security note
## 10）安全说明

Keys are read from your local env/files and used by your local process.
key 从你本地环境变量/配置文件读取，由你的本地进程使用。

loam does not require sending your provider key to project maintainers.
loam 不要求把你的上游 key 发送给项目维护者。

You should still revoke any key that was ever exposed in chat or screenshots.
但凡 key 在聊天或截图中暴露过，都建议立即吊销并重发。