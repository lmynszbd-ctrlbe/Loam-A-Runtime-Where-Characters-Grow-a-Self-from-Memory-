# loam — 不是“写人设”，而是“让角色从记忆长出自我”

> **A runtime where characters grow a self from memory.**

loam 是一个“角色记忆运行时”：
- 不把人格锁死在一段设定词里
- 把每一轮真实对话原文沉淀为可追溯记忆
- 让“变化”来自经历，而不是模板

它的核心目标是：
**原文不丢、变化可审计、人格可重建、与模型解耦。**

---

## 你得到的能力

- **L0 原始日记永久保存**（user/assistant 原文轮次）
- **L1-L4 派生层分离**（可重算，不污染原始事实）
- **后台持续生长线程**（有 API + model 时）
- **强制流程代理**（不依赖 Agent 是否调用工具）
- **多上游聚合路由**（`provider/model` 一入口切换多家中转）
- **Termux 一键运维脚本**（start/status/stop/log + final 一键总控）

---

## 目录结构（核心）

- `loam/`：核心运行时（store/core/mind/server/cli）
- `bridge/forced_flow_proxy.py`：OpenAI 兼容强制流程代理
- `scripts/termux/`：Termux 启停、状态、日志、开机自启、最终总控
- `tests/`：单元 + 集成测试
- `FINAL_RELEASE.md`：最终版启动说明
- `TERMUX_QUICKSTART.md`：Termux 快速开始
- `THIRD_PARTY_INTEGRATION.md`：三方接入说明
- `MULTI_UPSTREAM_QUICKSTART.md`：多上游配置说明

---

## 一条命令启动（Termux 最终版）

> 前提：你已在 `~/.loam/upstreams.json` 配好上游；并准备好 `LOAM_API_KEY` 与 `LOAM_MODEL`。

```bash
cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh
```

状态查看：
```bash
cd ~/loam && bash scripts/termux/final_status_all.sh
```

停止：
```bash
cd ~/loam && bash scripts/termux/final_stop_all.sh
```

---

## 三方 Agent 接入（推荐）

把 Agent 的 OpenAI 兼容 Base URL 指向：

- `http://<你的主机>:8780/v1`

然后模型名用：

- `provider/model`（例如 `deepseek/deepseek-chat`、`openai/gpt-4o-mini`）

代理会强制执行：
1. 先向 loam 请求上下文
2. 再调用上游模型
3. 最后把本轮 **原文** 回写 loam

所以不会出现“模型没调工具就丢记忆”。

---

## 本地验证

```bash
cd /home/loam
python tests/test_integration.py
python e2e_smoke.py
```

---

## 项目定位

loam 不是“提示词皮肤工程”。
它是一层可长期运行、可审计、可迁移的记忆底座：

- 角色可以换模型，不丢“自己”
- 上游可以换渠道，不改核心记忆逻辑
- 回看任何变化，都能追溯到原始经历

**别写人设，让“我”长出来。**
