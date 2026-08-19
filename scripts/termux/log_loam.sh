#!/data/data/com.termux/files/usr/bin/bash
# loam 日志查看脚本（Termux）

set -u

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
LOG_FILE="$LOAM_HOME/run/loam.log"

if [ ! -f "$LOG_FILE" ]; then
  echo "日志不存在: $LOG_FILE"
  exit 0
fi

tail -n 200 -f "$LOG_FILE"