#!/data/data/com.termux/files/usr/bin/bash
# loam 停止脚本（Termux）

set -u

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
PID_FILE="$LOAM_HOME/run/loam.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "未找到 pid 文件，可能未运行"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$pid" ]; then
  echo "pid 文件为空，已清理"
  rm -f "$PID_FILE"
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  echo "已停止 loam (pid=$pid)"
else
  echo "进程不存在，清理残留 pid 文件"
fi

rm -f "$PID_FILE"