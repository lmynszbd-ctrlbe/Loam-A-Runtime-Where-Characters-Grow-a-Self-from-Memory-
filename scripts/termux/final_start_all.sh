#!/data/data/com.termux/files/usr/bin/bash
# loam 一键启动：所有内部服务由 start.py 管理，只对外暴露统一网关端口

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
LOAM_CHARACTER="${LOAM_CHARACTER:-default}"
LOAM_PORT="${LOAM_PORT:-8765}"
UNIFIED_PORT="${UNIFIED_PORT:-8783}"
PROXY_PORT="${PROXY_PORT:-8781}"

# 让子脚本共用这些环境变量
export LOAM_HOME
export LOAM_CHARACTER
export LOAM_PORT

# 上游配置（多上游优先）
UPSTREAMS_CONFIG="${UPSTREAMS_CONFIG:-$LOAM_HOME/upstreams.json}"
UPSTREAM_DEFAULT="${UPSTREAM_DEFAULT:-}"
UPSTREAM_BASE_URL="${UPSTREAM_BASE_URL:-}"
UPSTREAM_API_KEY="${UPSTREAM_API_KEY:-}"
UPSTREAM_MODEL="${UPSTREAM_MODEL:-}"

export UPSTREAMS_CONFIG
export UPSTREAM_DEFAULT
export UPSTREAM_BASE_URL
export UPSTREAM_API_KEY
export UPSTREAM_MODEL
export PROXY_PORT
export UNIFIED_PORT
export UNIFIED_HOST="${UNIFIED_HOST:-0.0.0.0}"
export PROXY_HOST="127.0.0.1"
export ADMIN_HOST="127.0.0.1"

cd "$REPO_DIR" || {
  echo "无法进入项目目录: $REPO_DIR"
  exit 1
}

if ! command -v python >/dev/null 2>&1; then
  echo "未找到 python，请先执行: pkg install python -y"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "未找到 curl，请先执行: pkg install curl -y"
  exit 1
fi

echo "[1/2] 启动完整单端口栈"
cd "$REPO_DIR" || exit 1
nohup env LOAM_HOME="$LOAM_HOME" python start.py > "$LOAM_HOME/run/loam-stack.log" 2>&1 &
echo $! > "$LOAM_HOME/run/stack.pid"
sleep 2

echo "[2/2] 检查统一网关"
HEALTH="$(curl -s "http://127.0.0.1:$UNIFIED_PORT/health" || true)"
if [ -z "$HEALTH" ]; then
  echo "统一网关健康检查失败，请查看 $LOAM_HOME/run/loam-stack.log"
  exit 1
fi
echo "$HEALTH"

echo
echo "✅ 全部启动完成（仅对外端口 $UNIFIED_PORT）"
echo "Agent 配置："
echo "  Base URL: http://127.0.0.1:$UNIFIED_PORT/v1"
echo "  Model:    provider/model（例如 relayA/gpt-4o-mini）"
echo
echo "管理命令："
echo "  bash $SCRIPT_DIR/final_status_all.sh"
echo "  bash $SCRIPT_DIR/final_stop_all.sh"