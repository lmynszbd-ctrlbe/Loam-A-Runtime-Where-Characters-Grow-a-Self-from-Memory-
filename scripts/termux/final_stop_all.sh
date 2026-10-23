#!/data/data/com.termux/files/usr/bin/bash
# 一键停止单端口栈与所有子服务

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
STACK_PID_FILE="$LOAM_HOME/run/stack.pid"

if [ -f "$STACK_PID_FILE" ]; then
  pid="$(cat "$STACK_PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$STACK_PID_FILE"
fi

if [ -f "$REPO_DIR/scripts/reset.sh" ]; then
  bash "$REPO_DIR/scripts/reset.sh" || true
else
  bash "$SCRIPT_DIR/stop_forced_proxy.sh" || true
  bash "$SCRIPT_DIR/stop_loam.sh" || true
fi

echo "已执行停止流程"
