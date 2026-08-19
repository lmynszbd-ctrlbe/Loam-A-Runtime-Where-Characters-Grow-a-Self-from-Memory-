#!/data/data/com.termux/files/usr/bin/bash
# loam 状态脚本（Termux）

set -u

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
HOST="${LOAM_HOST:-127.0.0.1}"
PORT="${LOAM_PORT:-8765}"
PID_FILE="$LOAM_HOME/run/loam.pid"
LOG_FILE="$LOAM_HOME/run/loam.log"

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "进程: 运行中 (pid=$pid)"
  else
    echo "进程: 未运行（pid 文件残留）"
  fi
else
  echo "进程: 未运行"
fi

if command -v curl >/dev/null 2>&1; then
  echo "健康检查:"
  curl -s "http://$HOST:$PORT/health" || echo "无法连接"
  echo
else
  echo "健康检查: 未安装 curl（可 pkg install curl）"
fi

echo "日志文件: $LOG_FILE"