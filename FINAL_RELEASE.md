# loam Final Deployment Playbook (Launch Ready)

This playbook covers complete deployment from zero to production-like operation, including Termux, Linux server, desktop dev, and containerized scenarios.
本手册覆盖从零到可上线的完整部署路径，包含 Termux、Linux 服务器、桌面开发与容器化场景。

> If you are a complete beginner, read this first:
> `docs/DEPLOYMENT_FOR_ABSOLUTE_BEGINNERS.md`
>
> 如果你是零基础用户，请先看：
> `docs/DEPLOYMENT_FOR_ABSOLUTE_BEGINNERS.md`

---

## 1) Architecture in one paragraph

The runtime has two cooperating services: `loam` (memory storage + digest + growth + context) and `forced proxy` (OpenAI-compatible gateway that enforces `/context -> upstream -> /ingest` every turn). Your client talks only to local proxy URL, while proxy routes to real upstream providers by provider mapping.

整套运行时由两个协同服务组成：`loam`（记忆存储 + 消化 + 生长 + 上下文）与 `forced proxy`（OpenAI 兼容网关，强制每轮执行 `/context -> upstream -> /ingest`）。你的客户端只连接本地代理 URL，代理再按 provider 映射转发到真实上游。

---

## 2) Deployment mode selection

Choose Termux if you want a phone-based personal always-on setup; choose Linux server/VM for long-running stability and process supervision; choose WSL/macOS for local feature development and debugging; choose containerized deployment for reproducibility across teammates. Functionally they are equivalent: same memory model, same growth logic, same API semantics.

如果你要手机个人常驻，选 Termux；如果你要长期稳定和进程托管，选 Linux 服务器/虚拟机；如果你要本地开发调试，选 WSL/macOS；如果你要团队环境一致性，选容器化。它们在功能上等价：同一记忆模型、同一生长逻辑、同一 API 语义。

---

## 3) Universal prerequisites

Install Python 3.10+ and curl, clone repository, and ensure your runtime can read/write `~/.loam`. Then prepare upstream provider credentials (base URL + API key + default model). If you do not have upstream credentials, routing cannot complete.

先安装 Python 3.10+ 与 curl，克隆仓库，并确保运行环境可读写 `~/.loam`。随后准备上游提供方凭证（base URL + API key + default model）。如果没有上游凭证，路由无法完成。

---

## 4) Upstream mapping (required)

The upstream template is the sample file in this repository: `~/loam/bridge/upstreams.example.json`. It contains placeholders only, so copy it into runtime path and replace values with your real provider settings. The `default` field is fallback provider, while each provider block defines request destination and auth. This file is the core of multi-upstream routing.

上游模板就是仓库里的示例文件：`~/loam/bridge/upstreams.example.json`。其中都是占位值，必须先复制到运行路径，再替换成真实 provider 参数。`default` 代表默认回退上游，每个 provider 块定义请求目标与鉴权信息。这份文件是多上游路由的核心。

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
python -m json.tool ~/.loam/upstreams.json >/dev/null && echo JSON_OK
```

---

## 5) Termux one-command startup

Use this path for fastest launch on Android. The script boots loam first, then proxy, and finally runs health checks. After startup, configure your client to local proxy URL and choose model in `provider/model` format.

这是 Android 上最快的上线路径。脚本会先启动 loam，再启动代理，并自动做健康检查。启动后在客户端填写本地代理 URL，模型名使用 `provider/model` 格式。

```bash
cd ~/loam
LOAM_API_KEY='your_loam_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

---

## 6) Linux/WSL/macOS startup (manual)

For non-Termux environments, start loam and proxy in two terminals or background services. Keep loam on 8765 and proxy on 8780 unless you have custom port policy. For production Linux, use process managers to auto-restart on crash.

在非 Termux 环境中，请分别启动 loam 与 proxy（可用两个终端或后台服务）。默认保持 loam=8765、proxy=8780，除非你有自定义端口策略。生产 Linux 建议使用进程管理器实现异常自动拉起。

```bash
python -m loam init-secrets --secrets-home ~/.loam
python -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
UPSTREAMS_CONFIG=$HOME/.loam/upstreams.json UPSTREAM_DEFAULT=relayA python bridge/forced_flow_proxy.py
```

---

## 7) Client-side fields (what to fill and why)

Set client Base URL to `http://127.0.0.1:8780/v1` so requests pass through forced pipeline. Client API key can be any non-empty placeholder if UI requires it; real provider credentials are read by local proxy from your upstream config. In multi-upstream mode, model must be `provider/model` (for example `relayA/gpt-4o-mini`).

客户端 Base URL 填 `http://127.0.0.1:8780/v1`，这样请求会经过强制流水线。客户端 API key 若必须非空，可填任意占位值；真实上游凭证由本地代理从配置文件读取。多上游模式下模型名必须是 `provider/model`（如 `relayA/gpt-4o-mini`）。

---

## 8) Health verification

A healthy stack should return JSON on both health endpoints and list at least one model from `/v1/models`. If models are empty, upstream URL/key/model is usually misconfigured. If proxy process exits immediately, check `~/.loam/run/forced_proxy.log`.

健康状态应满足：两个 health 接口都返回 JSON，且 `/v1/models` 至少有一个模型。如果模型列表为空，通常是上游 URL/key/model 配错；若 proxy 启动后立刻退出，请查看 `~/.loam/run/forced_proxy.log`。

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

---

## 9) Security boundary

Provider keys remain in your local files/environment and are used by your local runtime process to call your chosen upstream providers. The project does not require sending provider keys to maintainers, and normal runtime does not depend on a maintainer-hosted mandatory cloud relay. Your residual risk comes from your own host hardening, plugin chain, and secret management practices.

上游 key 保留在你本地文件/环境变量中，由你本地运行进程发往你选择的上游提供方。项目不要求把 provider key 发送给维护者，常规运行也不依赖维护者托管的强制云端中继。剩余风险主要来自你自己的主机加固、插件链路与密钥管理实践。

---

## 10) Daily operations

Use status/stop/start scripts in Termux mode, or your process manager in Linux mode. Keep one log source for loam and one for proxy, and treat model-routing failures as configuration incidents first, code incidents second.

Termux 模式下使用 status/stop/start 脚本，Linux 模式下使用进程管理器统一管控。建议 loam 与 proxy 分开看日志，并优先将模型路由失败视为配置故障而非代码故障。