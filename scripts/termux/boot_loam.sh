#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot 调用入口

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 给系统一点时间恢复网络/Wi‑Fi
sleep 8

bash "$SCRIPT_DIR/start_loam.sh"