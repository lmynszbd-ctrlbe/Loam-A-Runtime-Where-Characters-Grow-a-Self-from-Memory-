#!/data/data/com.termux/files/usr/bin/bash
# 一键停止：先 proxy 后 loam

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/stop_forced_proxy.sh" || true
bash "$SCRIPT_DIR/stop_loam.sh" || true

echo "已执行停止流程"