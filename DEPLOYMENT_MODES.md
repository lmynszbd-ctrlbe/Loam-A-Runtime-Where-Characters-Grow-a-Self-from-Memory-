# loam Deployment Modes

This document explains non-Termux deployment options and when to choose each mode.
本文件解释 Termux 之外的部署方式，以及每种方式的适用场景。

---

## 1) Termux on Android

Use this mode when you want personal, mobile, always-on operation on one phone. It is the fastest path to launch and requires the least system administration. You run startup scripts under `scripts/termux/` and keep data under `~/.loam` in Termux storage.

当你希望在单台手机上实现个人常驻运行时，选择这个模式。它上线最快、运维负担最小。你通过 `scripts/termux/` 下脚本启动，数据默认保存在 Termux 的 `~/.loam` 目录。

---

## 2) Linux server / VM

Use this mode for stable long-running service, team sharing, and better process supervision. Install Python 3.10+, clone repository, initialize secrets, then run `python -m loam run` and `python bridge/forced_flow_proxy.py` as background services. For production, use `systemd` or process managers (supervisord/pm2) to ensure restart-on-failure.

当你需要长期稳定运行、团队共享或更可控的进程治理时，选择 Linux 服务器/虚拟机模式。安装 Python 3.10+ 后克隆仓库，初始化 secrets，再分别启动 `python -m loam run` 与 `python bridge/forced_flow_proxy.py`。生产环境建议用 `systemd` 或进程管理器（supervisord/pm2）托管并自动拉起。

Example commands:
示例命令：

```bash
python -m loam init-secrets --secrets-home ~/.loam
python -m loam run --character default --home ~/.loam/characters --secrets-home ~/.loam --host 127.0.0.1 --port 8765
UPSTREAMS_CONFIG=$HOME/.loam/upstreams.json UPSTREAM_DEFAULT=relayA python bridge/forced_flow_proxy.py
```

---

## 3) WSL / macOS local development

Use this mode for development, debugging, and feature testing on desktop. The runtime behavior is identical to Linux mode; the main difference is how you install dependencies and manage shell startup. Keep local loopback endpoints (`127.0.0.1`) and test integration with your desktop client.

当你在桌面端做开发、调试或功能验证时，使用 WSL/macOS 模式。其运行逻辑与 Linux 基本一致，主要差异在依赖安装和 Shell 管理方式。建议保持本地回环地址（`127.0.0.1`）并配合桌面客户端进行联调。

---

## 4) Containerized deployment

Use this mode when you need reproducibility across teammates or environments. Mount `~/.loam` (or an equivalent persistent volume) into the container, inject required environment variables, and expose local ports 8765/8780 according to your architecture. If you containerize, keep secrets outside the image and pass them at runtime.

当你需要团队间环境一致性和可复现部署时，使用容器化模式。请把 `~/.loam`（或等效持久卷）挂载到容器中，在运行时注入环境变量，并根据架构暴露 8765/8780 端口。容器化时不要把密钥写进镜像，应在运行时注入。

---

## Mode differences at a glance

Termux optimizes convenience, Linux optimizes stability, WSL/macOS optimizes development speed, and containers optimize reproducibility. All modes share the same memory model, growth formula, forced pipeline, and upstream routing semantics.

Termux 强调便捷，Linux 强调稳定，WSL/macOS 强调开发效率，容器强调环境一致性。无论哪种模式，记忆模型、生长公式、强制流程和上游路由语义都保持一致。