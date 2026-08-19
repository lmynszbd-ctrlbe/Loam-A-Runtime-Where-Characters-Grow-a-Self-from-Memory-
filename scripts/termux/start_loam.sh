#!/data/data/com.termux/files/usr/bin/bash
# loam 持续运行启动脚本（Termux）

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
CHARACTER="${LOAM_CHARACTER:-default}"
PORT="${LOAM_PORT:-8765}"
HOST="${LOAM_HOST:-127.0.0.1}"

RUN_DIR="$LOAM_HOME/run"
LOG_FILE="$RUN_DIR/loam.log"
PID_FILE="$RUN_DIR/loam.pid"

mkdir -p "$RUN_DIR"
mkdir -p "$LOAM_HOME/characters"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "loam 已在运行中 (pid=$old_pid)"
    exit 0
  fi
fi

cd "$REPO_DIR" || {
  echo "无法进入项目目录: $REPO_DIR"
  exit 1
}

# 启动前做一次快速可运行检查
python -m loam --help >/dev/null 2>&1 || {
  echo "python -m loam 不可运行，请先检查 Python 环境"
  exit 1
}
# 必须检测到后台反思模型 key 才允许启动。
# （你现在要的是“持续自生长模式”，不是仅落盘模式）
HAS_KEY="${LOAM_API_KEY:-}"
HAS_MODEL="${LOAM_MODEL:-}"

if [ -z "$HAS_KEY" ] || [ -z "$HAS_MODEL" ]; then
  eval "$(python - "$LOAM_HOME" <<'PY'
import json,sys
from pathlib import Path
home=Path(sys.argv[1]).expanduser()
p=home/'secrets.json'
key=''
model=''
if p.exists():
    try:
        d=json.loads(p.read_text(encoding='utf-8'))
        key=(d.get('api_key') or '').strip()
        model=(d.get('model') or '').strip()
    except Exception:
        pass
# 用 shell 安全的单引号包起来
key=key.replace("'", "'\\''")
model=model.replace("'", "'\\''")
print(f"SECRETS_KEY='{key}'")
print(f"SECRETS_MODEL='{model}'")
PY
)"

  if [ -z "$HAS_KEY" ]; then
    HAS_KEY="${SECRETS_KEY:-}"
  fi
  if [ -z "$HAS_MODEL" ]; then
    HAS_MODEL="${SECRETS_MODEL:-}"
  fi
fi

if [ -z "$HAS_KEY" ]; then
  echo "启动失败：未检测到 LOAM_API_KEY（环境变量或 $LOAM_HOME/secrets.json）"
  echo "请先配置 key，再启动 loam。"
  exit 1
fi

if [ -z "$HAS_MODEL" ]; then
  echo "启动失败：未检测到 LOAM_MODEL（环境变量或 $LOAM_HOME/secrets.json）"
  exit 1
fi

case "$HAS_MODEL" in
  *flash*|*FLASH*|*Flash*) ;;
  *)
    echo "警告：你之前要求测试阶段优先 flash，当前模型='$HAS_MODEL'"
    ;;
esac

GROWER_ARG=""


nohup python -m loam run \
  --character "$CHARACTER" \
  --home "$LOAM_HOME/characters" \
  --secrets-home "$LOAM_HOME" \
  --host "$HOST" \
  --port "$PORT" \
  $GROWER_ARG \
  >>"$LOG_FILE" 2>&1 &

new_pid="$!"
echo "$new_pid" > "$PID_FILE"

sleep 1
if kill -0 "$new_pid" 2>/dev/null; then
  echo "loam 启动成功"
  echo "  pid: $new_pid"
  echo "  url: http://$HOST:$PORT/health"
  echo "  log: $LOG_FILE"
else
  echo "loam 启动失败，请查看日志: $LOG_FILE"
  exit 1
fi