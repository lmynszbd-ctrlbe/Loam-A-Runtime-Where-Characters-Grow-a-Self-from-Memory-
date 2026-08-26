"""持久化状态与常数覆盖管理器。

提供 ~/.loam/state/ 目录下的 overrides.json 与 startup 日志的原子读写与启动恢复能力。
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("loam.state")

SCHEMA_VERSION = 1


def resolve_state_dir(home: str | Path = "~/.loam") -> Path:
    """解析 state 目录路径并确保存在。"""
    p = Path(home).expanduser() / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def overrides_file_path(home: str | Path = "~/.loam") -> Path:
    """返回 overrides.json 的完整路径。"""
    return resolve_state_dir(home) / "overrides.json"


def load_persisted_overrides(home: str | Path = "~/.loam") -> Dict[str, Dict[str, Any]]:
    """从磁盘加载持久化的常数覆盖。
    
    返回字典格式: { "PLASTICITY": {"original": 0.35, "override": 0.45}, ... }
    如果文件不存在或解析失败，安全返回空字典，不阻塞主服务。
    """
    path = overrides_file_path(home)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("overrides.json 格式异常 (非 dict)，跳过加载: %s", path)
            return {}
        items = data.get("items", {})
        if isinstance(items, dict):
            return items
        return {}
    except Exception as exc:
        logger.warning("读取 overrides.json 失败 (%s)，使用默认值", exc)
        return {}


def save_persisted_overrides(
    items: Dict[str, Dict[str, Any]],
    home: str | Path = "~/.loam",
    cycle: int = 0,
) -> bool:
    """原子写入常数覆盖到磁盘。
    
    使用临时文件 + os.replace 保证进程崩溃或断电不会损坏文件。
    """
    state_dir = resolve_state_dir(home)
    target_path = state_dir / "overrides.json"
    payload = {
        "version": SCHEMA_VERSION,
        "applied_at": time.time(),
        "cycle_at_apply": cycle,
        "items": items,
    }
    try:
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(dir=str(state_dir), prefix="overrides_", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(target_path))
        return True
    except Exception as exc:
        logger.error("写入 overrides.json 失败: %s", exc)
        return False


def clear_persisted_overrides(home: str | Path = "~/.loam") -> bool:
    """清除持久化的常数覆盖文件。"""
    path = overrides_file_path(home)
    try:
        if path.exists():
            path.unlink()
        return True
    except Exception as exc:
        logger.error("删除 overrides.json 失败: %s", exc)
        return False


def apply_overrides_to_constants(
    items: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """将覆盖条目校验并写入 loam.core.constants 模块。
    
    返回 (applied, rejected)
    """
    import loam.core.constants as C

    applied: Dict[str, Any] = {}
    rejected: Dict[str, str] = {}

    for name, item in items.items():
        if not isinstance(name, str) or not name.isupper() or name.startswith("_"):
            rejected[name] = "invalid name"
            continue
        if not hasattr(C, name):
            rejected[name] = "not found"
            continue
        orig = getattr(C, name)
        # item 可以是 {"original": ..., "override": val} 也可以直接是 val
        val = item.get("override", item) if isinstance(item, dict) else item
        if not isinstance(orig, type(val)):
            rejected[name] = f"type mismatch: {type(orig).__name__} vs {type(val).__name__}"
            continue
        setattr(C, name, val)
        applied[name] = {"original": orig, "override": val}

    return applied, rejected


def record_startup_event(home: str | Path = "~/.loam", note: str = "") -> None:
    """向 state/startup.log 追加一行启动日志。"""
    try:
        log_path = resolve_state_dir(home) / "startup.log"
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        line = f"[{ts}] STARTUP: {note}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
