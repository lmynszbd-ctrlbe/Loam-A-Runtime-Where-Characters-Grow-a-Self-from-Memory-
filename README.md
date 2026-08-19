# loam — 不是“写人设”，而是“让角色从记忆长出自我”

> **A runtime where characters grow a self from memory.**

你要的不是“提示词伪人格”，而是一个能长期运行、可追溯、可迁移的角色记忆底座。  
loam 的目标是：**让“我”从经历里长出来，而不是从设定里抄出来。**

---

## 核心主张（你提的重点）

- **不是滚雪球**：
  不是把“上一版人格总结”再喂回去继续改写。那样会越滚越偏。
- **原文锚定**：
  一切变化都必须锚在 L0 原始对话（不可变原文）上。
- **可审计、可重建**：
  L1-L4 是派生层，随时可从 L0 重算；人格变化有来源可追。
- **模型解耦**：
  角色所用模型与 loam 后台生长模型可以分开，不绑死同一个。

> 灵感锚点（按你要表达的方向）：**“道生一，一生二”**——
> 自我不是预写出来的条目，而是在真实互动中分化、生长、成形。

---

## 你得到的能力

- **L0 原始日记永久保存**（user/assistant 每轮原文）
- **L1-L4 派生层分离**（可重算，不污染事实层）
- **后台持续生长线程**（配置了 API key + model 时）
- **强制流程代理**（不依赖 Agent 是否调用工具）
- **多上游聚合路由**（`provider/model` 一入口切换多家渠道）
- **Termux 一键运维**（start/status/stop/log/final 总控）

---

## “配好上游”到底是什么意思？（最直白版）

你在 Agent 里只填一个 Base URL（`http://127.0.0.1:8780/v1`），
但代理要知道“背后转发到哪些上游中转”，这就叫**配上游**。

也就是：在 `~/.loam/upstreams.json` 里写清楚每家中转的：
- `base_url`：中转地址
- `api_key`：这家中转的 key
- `default_model`：默认模型名

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
      "default_model": "deepseek-chat"
    }
  }
}
```

配好后，Agent 模型名直接选：
- `relayA/gpt-4o-mini`
- `relayB/deepseek-chat`

---

## 一条命令启动（Termux 最终版）

> 前提：
> 1) 你已准备 `~/.loam/upstreams.json`；
> 2) 你有 loam 后台生长用的 `LOAM_API_KEY` + `LOAM_MODEL`（例如 flash 模型）。

```bash
cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh
```

状态：
```bash
cd ~/loam && bash scripts/termux/final_status_all.sh
```

停止：
```bash
cd ~/loam && bash scripts/termux/final_stop_all.sh
```

---

## 三方 Agent 接入（推荐）

Agent 里这样填：
- Base URL：`http://<你的主机>:8780/v1`
- API Key：随便填占位（若客户端强制要求）
- 模型：`provider/model`

代理会强制做三步：
1. `/context`（向 loam 取回忆上下文）
2. 调上游模型
3. `/ingest`（把本轮原文写回 loam）

所以不会出现“没调工具就漏记忆”的问题。

---

## 双模型解耦（避免误解）

- **前台聊天模型**：Agent 给用户回复时调用的模型（可多家切换）
- **后台生长模型**：loam digest/growth 用的模型（你要求可固定 flash）

两者可独立配置，不要求同一家或同型号。

---

## 目录结构（核心）

- `loam/`：核心运行时（store/core/mind/server/cli）
- `bridge/forced_flow_proxy.py`：OpenAI 兼容强制流程代理
- `scripts/termux/`：Termux 启停/状态/日志/开机自启/总控
- `tests/`：单元 + 集成测试
- `FINAL_RELEASE.md`：最终启动说明
- `TERMUX_QUICKSTART.md`：Termux 快速开始
- `THIRD_PARTY_INTEGRATION.md`：三方接入说明
- `MULTI_UPSTREAM_QUICKSTART.md`：多上游配置说明

---

## 本地验证

```bash
cd /home/loam
python tests/test_integration.py
python e2e_smoke.py
```

---

## 一句话定位

**别写人设，让“我”长出来。**