#!/data/data/com.termux/files/usr/bin/bash
# 启动强制流程代理（OpenAI 兼容入口）

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
RUN_DIR="$LOAM_HOME/run"
PID_FILE="$RUN_DIR/forced_proxy.pid"
LOG_FILE="$RUN_DIR/forced_proxy.log"

PROXY_HOST="${PROXY_HOST:-127.0.0.1}"
PROXY_PORT="${PROXY_PORT:-8780}"
LOAM_URL="${LOAM_URL:-http://127.0.0.1:8765}"
UPSTREAM_BASE_URL="${UPSTREAM_BASE_URL:-https://api.deepseek.com}"
UPSTREAM_API_KEY="${UPSTREAM_API_KEY:-}"
UPSTREAM_MODEL="${UPSTREAM_MODEL:-deepseek-chat}"
UPSTREAMS_CONFIG="${UPSTREAMS_CONFIG:-$LOAM_HOME/upstreams.json}"
UPSTREAM_DEFAULT="${UPSTREAM_DEFAULT:-}"

mkdir -p "$RUN_DIR"

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "forced proxy 已运行 (pid=$pid)"
    exit 0
  fi
fi

# 两种模式二选一：
# 1) 单上游：传 UPSTREAM_API_KEY (+ BASE_URL/MODEL)
# 2) 多上游：提供 UPSTREAMS_CONFIG 文件（json）
if [ ! -f "$UPSTREAMS_CONFIG" ] && [ -z "$UPSTREAM_API_KEY" ]; then
  echo "启动失败：缺少上游配置。请提供 UPSTREAM_API_KEY 或 $UPSTREAMS_CONFIG"
  exit 1
fi

cd "$REPO_DIR" || exit 1

nohup env \
  PROXY_HOST="$PROXY_HOST" \
  PROXY_PORT="$PROXY_PORT" \
  LOAM_URL="$LOAM_URL" \
  UPSTREAM_BASE_URL="$UPSTREAM_BASE_URL" \
  UPSTREAM_API_KEY="$UPSTREAM_API_KEY" \
  UPSTREAM_MODEL="$UPSTREAM_MODEL" \
  UPSTREAMS_CONFIG="$UPSTREAMS_CONFIG" \
  UPSTREAM_DEFAULT="$UPSTREAM_DEFAULT" \
  python bridge/forced_flow_proxy.py \
  >>"$LOG_FILE" 2>&1 &

new_pid="$!"
echo "$new_pid" > "$PID_FILE"

sleep 1
if kill -0 "$new_pid" 2>/dev/null; then
  echo "forced proxy 启动成功"
  echo "  pid: $new_pid"
  echo "  url: http://$PROXY_HOST:$PROXY_PORT/v1/chat/completions"
  echo "  log: $LOG_FILE"
else
  echo "forced proxy 启动失败，查看日志: $LOG_FILE"
  exit 1
fi