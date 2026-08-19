#!/data/data/com.termux/files/usr/bin/bash

set -u

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
PID_FILE="$LOAM_HOME/run/forced_proxy.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "未找到 forced proxy pid 文件"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  echo "已停止 forced proxy (pid=$pid)"
else
  echo "forced proxy 进程不存在"
fi

rm -f "$PID_FILE"