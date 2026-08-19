# v0.1.0 — loam Final Runtime Release

> **不是“写人设”，而是“让角色从记忆长出自我”。**

“道生一，一生二”的灵感在这里落地为工程原则：
自我不是预设文本，而是在可追溯经历中分化、生长、稳定。

---

## 🔥 本版重点亮点

1. **非滚雪球人格演化**
   - 不把“上一版人格总结”当下一版真相
   - 变化始终锚定 L0 原始对话

2. **强制原文入库（抗工具不调用）**
   - 代理强制执行：`/context -> 上游模型 -> /ingest`
   - 每轮 user + assistant 原文都能落库

3. **单入口多上游**
   - Agent 只填一个 URL：`http://host:8780/v1`
   - 用 `provider/model` 在多家中转间切换

4. **双模型解耦**
   - 前台聊天模型与 loam 后台生长模型独立配置
   - 角色“自我延续”不绑死某个厂商模型

5. **可审计、可重建**
   - L0 永久保留
   - L1-L4 可重算，变化来源可追溯

---

## ✅ Included in v0.1.0

- Core runtime: `loam/`（store/core/mind/server/CLI）
- Forced proxy: `bridge/forced_flow_proxy.py`
- Multi-upstream example: `bridge/upstreams.example.json`
- Termux ops scripts: `scripts/termux/`
- Tests: `tests/`（含 integration + smoke）
- Docs:
  - `FINAL_RELEASE.md`
  - `TERMUX_QUICKSTART.md`
  - `THIRD_PARTY_INTEGRATION.md`
  - `MULTI_UPSTREAM_QUICKSTART.md`

---

## 🚀 Quick Start (Termux)

```bash
cd ~/loam && LOAM_API_KEY='你的key' LOAM_MODEL='deepseek-chat-flash' bash scripts/termux/final_start_all.sh
```

Status:

```bash
cd ~/loam && bash scripts/termux/final_status_all.sh
```

Stop:

```bash
cd ~/loam && bash scripts/termux/final_stop_all.sh
```

---

## ⚠ Behavior Notes

- 启动策略按最终偏好：**必须 API key + model**。
- 推荐使用强制流程代理，避免“工具调用概率”导致记忆漏写。

---

## 🧪 Verification

```bash
python tests/test_integration.py
python e2e_smoke.py
```

---

## 🔐 Security

- 如果 token 曾在聊天/日志中出现，请立即 revoke 并更换。