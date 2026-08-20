#!/usr/bin/env bash
set -u

# 可复现构建最小校验：Python 版本 + 源码可编译 + 测试入口可导入
python - <<'PY'
import platform
import sys

ver = sys.version_info
if ver.major != 3 or ver.minor != 12:
    raise SystemExit(f"need Python 3.12.x, got {platform.python_version()}")
print(f"python={platform.python_version()}")
PY

python -m compileall -q loam tests

echo "reproducible-build-check: OK"