#!/data/data/com.termux/files/usr/bin/bash
# 一键：初始化 + 写入 key/model + 启动 loam（Termux）

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOAM_HOME="${LOAM_HOME:-$HOME/.loam}"
mkdir -p "$LOAM_HOME"

echo "[1/5] 检查 Python"
if ! command -v python >/dev/null 2>&1; then
  echo "未找到 python，请先执行: pkg install python -y"
  exit 1
fi

echo "[2/5] 生成 secrets 模板（如不存在）"
cd "$REPO_DIR" || exit 1
python -m loam init-secrets --secrets-home "$LOAM_HOME" >/dev/null 2>&1 || {
  echo "生成 secrets 模板失败"
  exit 1
}

# 可通过环境变量写入 key/model
#   LOAM_API_KEY=... LOAM_MODEL=... bash bootstrap_and_start.sh
if [ -n "${LOAM_MODEL:-}" ]; then
  case "${LOAM_MODEL}" in
    *flash*|*FLASH*|*Flash*) ;;
    *)
      echo "警告：你要求测试阶段仅用 flash 模型，当前 LOAM_MODEL='${LOAM_MODEL}'"
      ;;
  esac
fi

if [ -n "${LOAM_API_KEY:-}" ] || [ -n "${LOAM_MODEL:-}" ] || [ -n "${LOAM_BASE_URL:-}" ]; then
  echo "[3/5] 写入 secrets（来自环境变量）"
  python - "$LOAM_HOME" <<'PY' || { echo "写入 secrets 失败"; exit 1; }
import json, os, sys
from pathlib import Path
home = Path(sys.argv[1]).expanduser()
path = home / "secrets.json"
obj = {}
if path.exists():
    obj = json.loads(path.read_text(encoding="utf-8"))
if os.environ.get("LOAM_API_KEY"):
    obj["api_key"] = os.environ["LOAM_API_KEY"]
if os.environ.get("LOAM_MODEL"):
    obj["model"] = os.environ["LOAM_MODEL"]
if os.environ.get("LOAM_BASE_URL"):
    obj["base_url"] = os.environ["LOAM_BASE_URL"]
path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
print(path)
PY
else
  echo "[3/5] 未提供环境变量，保持 secrets 现状"
fi

echo "[4/5] 校验 secrets（必须有 api_key + model）"
python - "$LOAM_HOME" <<'PY' || { echo "secrets 校验失败"; exit 1; }
import json,sys
from pathlib import Path
home=Path(sys.argv[1]).expanduser()
p=home/'secrets.json'
if not p.exists():
    print(f"缺少 {p}")
    raise SystemExit(1)
try:
    d=json.loads(p.read_text(encoding='utf-8'))
except Exception as e:
    print(f"secrets.json 解析失败: {e}")
    raise SystemExit(1)
key=(d.get('api_key') or '').strip()
model=(d.get('model') or '').strip()
if not key:
    print('缺少 api_key，请传 LOAM_API_KEY 或手动编辑 secrets.json')
    raise SystemExit(1)
if not model:
    print('缺少 model，请传 LOAM_MODEL 或手动编辑 secrets.json')
    raise SystemExit(1)
print('secrets 校验通过')
PY

echo "[5/5] 启动 loam"
bash "$SCRIPT_DIR/start_loam.sh" || { echo "loam 启动失败"; exit 1; }

echo
echo "完成。可用以下命令管理："
echo "  bash $SCRIPT_DIR/status_loam.sh"
echo "  bash $SCRIPT_DIR/log_loam.sh"
echo "  bash $SCRIPT_DIR/stop_loam.sh"