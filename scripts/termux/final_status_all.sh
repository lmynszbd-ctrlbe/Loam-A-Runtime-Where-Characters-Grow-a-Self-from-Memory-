#!/data/data/com.termux/files/usr/bin/bash
# 一键状态检查：单端口统一网关 + 内部服务

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
UNIFIED_PORT="${UNIFIED_PORT:-8783}"
STACK_PID_FILE="$LOAM_HOME/run/stack.pid"

echo "=== unified stack (port $UNIFIED_PORT) ==="
if [ -f "$STACK_PID_FILE" ]; then
  pid="$(cat "$STACK_PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "stack.py: 运行中 (pid=$pid)"
  else
    echo "stack.py: 未运行（pid 文件残留）"
  fi
fi

if command -v curl >/dev/null 2>&1; then
  echo "gateway health:"
  curl -s "http://127.0.0.1:$UNIFIED_PORT/health" || echo "无法连接"
  echo
fi

echo
echo "=== loam core ==="
bash "$SCRIPT_DIR/status_loam.sh" || true

echo
echo "=== forced proxy ==="
bash "$SCRIPT_DIR/status_forced_proxy.sh" || true
