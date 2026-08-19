# loam — 不是“写人设”，而是“让角色从记忆长出自我”

loam is a long-term memory runtime that keeps raw dialogue, builds derived memory layers, and drives identity growth over time.
loam 是一个长期记忆运行时：保存原始对话，构建可重算的派生记忆层，并让身份随时间持续生长。

It is designed for continuity-first character systems, companion agents, and role-based assistants that must remain stable across months.
它面向“连续性优先”的角色系统、陪伴型智能体和需要跨月稳定运行的身份化助手。

---

## What loam actually does
## loam 到底在做什么

loam stores every turn as immutable raw material, then digests it into narrative, traits, and retrievable context.
loam 会把每轮对话作为不可变原料保存，再逐步消化成叙事、特质与可检索上下文。

This means the system can remember, explain why it changed, and rebuild derived layers when models or rules change.
这意味着系统不仅能“记住”，还能解释“为什么会变成现在这样”，并在模型/规则变化时重建派生层。

Core capabilities include persistent memory, growth dynamics, auditability, and model decoupling.
核心能力包括：持久记忆、生长动力学、可审计追溯、模型解耦。

---

## Why this is different from persona prompting
## 这和“提示词写人设”有什么不同

Typical persona prompting keeps rewriting a summarized identity and eventually drifts.
常见提示词人设会反复改写“人格总结”，最后往往发生漂移。

loam uses a no-snowball invariant: meaningful updates must anchor to raw turns, not to the previous summary.
loam 使用“非滚雪球不变量”：关键更新必须锚定原始轮次，而不是上一版总结。

So identity continuity comes from evidence accumulation, not from recursive self-description.
因此，身份连续性来自证据累积，而不是自我描述的递归放大。

---

## Growth mechanism (quantitative accumulation -> qualitative shift)
## 生长机制（量变累积 -> 质变跃迁）

Trait change speed is endogenous and phase-sensitive, not globally throttled by an external limiter.
特质变化速度是内生且分阶段敏感的，不依赖外部“统一限速器”。

Capacity curve:
容量曲线：

`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`
`capacity = max(strength, seed_floor) * max(ceiling - strength, seed_floor)`

Per-event update:
单事件更新：

`delta = plasticity * capacity * signal * salience`
`delta = plasticity * capacity * signal * salience`

Gate threshold:
门控阈值：

`gate = max(gate_floor, gate_ratio * capacity)`
`gate = max(gate_floor, gate_ratio * capacity)`

Evidence first accumulates in `pending`; only after crossing gate is the trait committed.
证据会先累积在 `pending`；只有跨过门槛才会提交到特质强度。

This is why growth is gradual in daily interaction but can still cross phases after long accumulation.
这就是为什么系统在日常互动里是“渐进变化”，但长期累积后又能发生“阶段跃迁”。

---

## 10-minute beginner path (where to run + what to fill)
## 小白 10 分钟路径（在哪运行 + 填什么）

All commands below are run inside the **Termux terminal**, not in chat input and not in GitHub web UI.
下面所有命令都在 **Termux 终端** 里执行，不是在聊天输入框里，也不是在 GitHub 网页里执行。

### Step 0: Install runtime prerequisites
### 第 0 步：安装运行前置项

Install Termux first, then open Termux and run:
先安装 Termux，然后打开 Termux 执行：

```bash
pkg update -y
pkg install -y python git curl
```

### Step 1: Download project code
### 第 1 步：下载项目代码

```bash
cd ~
git clone https://github.com/lmynszbd-ctrlbe/Loam-A-Runtime-Where-Characters-Grow-a-Self-from-Memory-.git loam
cd ~/loam
```

### Step 2: Prepare upstream config (multi-upstream recommended)
### 第 2 步：准备上游配置（推荐多上游）

```bash
mkdir -p ~/.loam
cp ~/loam/bridge/upstreams.example.json ~/.loam/upstreams.json
nano ~/.loam/upstreams.json
```

In `nano`, replace placeholder values with your real provider info, then press `Ctrl+O`, `Enter`, `Ctrl+X`.
在 `nano` 里把占位值替换成你的真实上游信息，然后按 `Ctrl+O`、`Enter`、`Ctrl+X` 保存退出。

### Step 3: Start loam + forced proxy in one command
### 第 3 步：一条命令启动 loam + 强制代理

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
UPSTREAMS_CONFIG="$HOME/.loam/upstreams.json" \
UPSTREAM_DEFAULT='relayA' \
bash scripts/termux/final_start_all.sh
```

`LOAM_API_KEY` is for loam's internal digest/growth model, not for your chat UI directly.
`LOAM_API_KEY` 是给 loam 内部消化/生长模型使用的，不是给聊天 UI 直接调用的。

### Step 4: Fill your Agent settings
### 第 4 步：填写你的 Agent 设置

Base URL: `http://127.0.0.1:8780/v1`
Base URL：`http://127.0.0.1:8780/v1`

API key: any placeholder if your client requires one.
API key：如果客户端强制要求，可填任意占位值。

Model: `provider/model`, e.g. `relayA/gpt-4o-mini`.
Model：`provider/model` 格式，例如 `relayA/gpt-4o-mini`。

### Step 5: Verify service health
### 第 5 步：验证服务状态

```bash
cd ~/loam
bash scripts/termux/final_status_all.sh
curl -s http://127.0.0.1:8780/health
curl -s http://127.0.0.1:8780/v1/models
```

If health returns JSON and models list is non-empty, setup is complete.
如果健康检查返回 JSON，且模型列表非空，就说明配置已完成。

---

## URL/API fields explained (what they are and why needed)
## URL/API 字段解释（是什么、为什么要填）

`LOAM_API_KEY` authenticates loam's own digest/growth calls to its configured model provider.
`LOAM_API_KEY` 用于 loam 内部消化/生长调用时的鉴权。

`UPSTREAM base_url/api_key/model` tells the forced proxy where to forward chat completion requests.
`UPSTREAM 的 base_url/api_key/model` 用于告诉强制代理把聊天请求转发到哪里。

Agent `Base URL` points to local proxy so every turn can be forced through `/context -> upstream -> /ingest`.
Agent 的 `Base URL` 指向本地代理，是为了确保每轮都经过 `/context -> 上游 -> /ingest` 强制流程。

Without URL/API mapping, proxy cannot route, and your client cannot reach usable models.
如果不填写 URL/API 映射，代理无法路由，你的客户端也无法拿到可用模型。

---

## Security boundary (important)
## 安全边界（重要）

Your provider keys are stored in your local env/files by default.
你的上游 key 默认保存在你自己的本地环境变量/配置文件里。

Requests are sent from your local process directly to your selected upstream endpoints.
请求由你的本地进程直接发往你选择的上游端点。

The project does not require uploading your provider keys to maintainers.
项目本身不要求把你的上游 key 上传给维护者。

You still need to protect your own host, plugins, and config files.
你仍然需要保护自己的主机环境、插件与配置文件。

---

## Documentation map
## 文档导航

Read `TERMUX_QUICKSTART.md` for absolute beginner setup details.
看 `TERMUX_QUICKSTART.md` 获取面向小白的完整安装与启动步骤。

Read `MULTI_UPSTREAM_QUICKSTART.md` for multi-provider routing and model naming rules.
看 `MULTI_UPSTREAM_QUICKSTART.md` 获取多上游路由与模型命名规则。

Read `THIRD_PARTY_INTEGRATION.md` for MCP/plugin/script integration patterns.
看 `THIRD_PARTY_INTEGRATION.md` 获取 MCP/插件/脚本接入模式。

Read `INTEGRATION_CHECKLIST.md` before release rollout.
上线前请按 `INTEGRATION_CHECKLIST.md` 做完整检查。

Don’t script a persona; build a memory-grounded self.
不要脚本化“人设”，要让“自我”在记忆中生长出来。
