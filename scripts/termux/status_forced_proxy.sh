#!/data/data/com.termux/files/usr/bin/bash

set -u

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
PID_FILE="$LOAM_HOME/run/forced_proxy.pid"
LOG_FILE="$LOAM_HOME/run/forced_proxy.log"
PROXY_HOST="${PROXY_HOST:-127.0.0.1}"
PROXY_PORT="${PROXY_PORT:-8780}"

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "forced proxy: 运行中 (pid=$pid)"
  else
    echo "forced proxy: 未运行（pid 文件残留）"
  fi
else
  echo "forced proxy: 未运行"
fi

if command -v curl >/dev/null 2>&1; then
  echo "health:"
  curl -s "http://$PROXY_HOST:$PROXY_PORT/health" || echo "无法连接"
  echo
fi

echo "log: $LOG_FILE"