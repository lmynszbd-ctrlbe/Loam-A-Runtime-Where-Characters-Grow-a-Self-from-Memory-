# v0.1.0 — Loam Final Runtime Release

> **不是“写人设”，而是“让角色从记忆长出自我”。**

## Why this matters

大多数“人格系统”会滚雪球：
把上一版总结继续喂给下一版，长期会自我漂移。

loam 的原则是：
- **原文锚定**：变化依据始终回到 L0 原始对话
- **非滚雪球**：不把“上一版人格总结”当唯一真相
- **可审计**：任何变化都能追溯到经历来源

---

## Highlights

- ✅ 完整 loam 运行时（store/core/mind/server/CLI）
- ✅ L0 原始日记永久保留，L1-L4 派生层可重建
- ✅ 强制流程代理（不依赖 Agent 是否调用工具）
- ✅ 多上游聚合路由（`provider/model`）
- ✅ Termux 最终版运维脚本（start/status/stop/log + final 总控）
- ✅ 单元/集成/冒烟测试链路完成

---

## What’s Included

- Core runtime: `loam/`
- Forced proxy: `bridge/forced_flow_proxy.py`
- Termux ops scripts: `scripts/termux/`
- Tests: `tests/`
- Docs:
  - `FINAL_RELEASE.md`
  - `TERMUX_QUICKSTART.md`
  - `THIRD_PARTY_INTEGRATION.md`
  - `MULTI_UPSTREAM_QUICKSTART.md`

---

## Quick Start (Termux)

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

## Breaking / Behavior Notes

- 启动脚本按最终偏好：**必须 API key + model**。
- 推荐由代理强制写入每轮原文，规避工具调用不稳定。

---

## Verification

```bash
python tests/test_integration.py
python e2e_smoke.py
```

---

## Security

- 若 token 曾暴露于聊天/日志，请立即 revoke 并更换。