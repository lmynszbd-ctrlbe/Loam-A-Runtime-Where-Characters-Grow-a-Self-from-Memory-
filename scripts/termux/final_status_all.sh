#!/data/data/com.termux/files/usr/bin/bash
# 一键状态：loam + proxy

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== loam ==="
bash "$SCRIPT_DIR/status_loam.sh" || true

echo
echo "=== forced proxy ==="
bash "$SCRIPT_DIR/status_forced_proxy.sh" || true