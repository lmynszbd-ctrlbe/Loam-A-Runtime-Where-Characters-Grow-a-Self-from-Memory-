# loam on Termux (Quickstart)

This guide gives minimal commands for persistent local runtime.
这份指南提供最小命令集，用于本地常驻运行。

---

## Install dependencies
## 安装依赖

```bash
pkg update -y
pkg install -y python curl git
```

```bash
pkg update -y
pkg install -y python curl git
```

Install Termux:Boot if you want auto-start on device reboot.
若你希望设备重启后自动启动，请安装 Termux:Boot。

---

## Bootstrap and start
## 初始化并启动

Run from repository root (assume `~/loam`).
在仓库根目录执行（假设在 `~/loam`）。

```bash
cd ~/loam
LOAM_API_KEY='your_growth_key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/bootstrap_and_start.sh
```

```bash
cd ~/loam
LOAM_API_KEY='你的生长key' \
LOAM_MODEL='deepseek-chat-flash' \
bash scripts/termux/bootstrap_and_start.sh
```

`LOAM_MODEL` should be your chosen flash model id.
`LOAM_MODEL` 建议填写你指定的 flash 模型 id。

Secrets are written to `~/.loam/secrets.json` locally.
密钥会写入本地 `~/.loam/secrets.json`。

---

## Daily management commands
## 日常管理命令

```bash
cd ~/loam
bash scripts/termux/status_loam.sh
bash scripts/termux/log_loam.sh
bash scripts/termux/stop_loam.sh
bash scripts/termux/start_loam.sh
```

```bash
cd ~/loam
bash scripts/termux/status_loam.sh
bash scripts/termux/log_loam.sh
bash scripts/termux/stop_loam.sh
bash scripts/termux/start_loam.sh
```

---

## Optional boot auto-start
## 可选：开机自启

```bash
cd ~/loam
bash scripts/termux/install_boot.sh
```

```bash
cd ~/loam
bash scripts/termux/install_boot.sh
```

Reboot phone then re-check status.
手机重启后再检查状态。

---

## Quick health check
## 快速健康检查

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/stats
```

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/stats
```

If JSON returns, the service is running.
如果返回 JSON，说明服务正在运行。

---

## Security note
## 安全说明

Keys are local to your Termux environment unless you explicitly copy/share them.
除非你主动复制或分享，否则 key 仅存在于你的 Termux 本地环境。

loam does not require uploading your keys to maintainers.
loam 不要求你把 key 上传给维护者。