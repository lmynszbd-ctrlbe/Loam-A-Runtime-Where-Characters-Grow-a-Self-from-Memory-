#!/data/data/com.termux/files/usr/bin/bash
# loam 最终版一键启动：先 loam，再 forced proxy，并做健康检查

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
LOAM_CHARACTER="${LOAM_CHARACTER:-default}"
LOAM_PORT="${LOAM_PORT:-8765}"
PROXY_PORT="${PROXY_PORT:-8780}"

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

echo "[1/4] 启动 loam（必须 key+model）"
bash "$SCRIPT_DIR/bootstrap_and_start.sh" || exit 1

echo "[2/4] 启动 forced proxy"
bash "$SCRIPT_DIR/start_forced_proxy.sh" || exit 1

echo "[3/4] 健康检查 loam"
LOAM_HEALTH="$(curl -s "http://127.0.0.1:$LOAM_PORT/health" || true)"
if [ -z "$LOAM_HEALTH" ]; then
  echo "loam 健康检查失败"
  exit 1
fi
echo "$LOAM_HEALTH"

echo "[4/4] 健康检查 proxy + 模型列表"
PROXY_HEALTH="$(curl -s "http://127.0.0.1:$PROXY_PORT/health" || true)"
if [ -z "$PROXY_HEALTH" ]; then
  echo "proxy 健康检查失败"
  exit 1
fi
echo "$PROXY_HEALTH"

# models 只展示前几行，避免太长
curl -s "http://127.0.0.1:$PROXY_PORT/v1/models" | sed -n '1,40p'

echo
echo "✅ 全部启动完成"
echo "Agent 配置："
echo "  Base URL: http://127.0.0.1:$PROXY_PORT/v1"
echo "  Model:    provider/model（例如 relayA/gpt-4o-mini）"
echo
echo "管理命令："
echo "  bash $SCRIPT_DIR/final_status_all.sh"
echo "  bash $SCRIPT_DIR/final_stop_all.sh"