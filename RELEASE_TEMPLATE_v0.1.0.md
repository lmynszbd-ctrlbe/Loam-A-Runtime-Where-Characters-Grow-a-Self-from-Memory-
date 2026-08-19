# v0.1.0 — Loam Final Runtime Release

> **不是“写人设”，而是“让角色从记忆长出自我”。**

## Highlights

- ✅ 完整 loam 运行时（store/core/mind/server/CLI）
- ✅ L0 原始日记永久保留，L1-L4 派生层可重建
- ✅ 强制流程代理（不依赖 Agent 是否调用工具）
- ✅ 多上游聚合路由（`provider/model`）
- ✅ Termux 最终版运维脚本（start/status/stop/log + final 总控）
- ✅ 单元/集成/冒烟测试链路完成

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

## Breaking / Behavior Notes

- 启动脚本已按最终偏好切回：**必须提供 API key + model**。
- 推荐通过代理写入每轮原文，避免工具调用不稳定导致漏记忆。

## Verification

```bash
python tests/test_integration.py
python e2e_smoke.py
```

## Known TODO

- GitHub Release 页面可继续补充截图与演示视频
- 可追加日志轮转/守护重启等运维增强

## Security

- 若曾在聊天或日志中暴露 token，请立即 revoke 并更换。
