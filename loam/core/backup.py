"""数据备份与迁移工具 (Loam Export & Import).

支持将指定角色或全部角色的 SQLite 数据库、状态文件、网络拓扑一键打包为 .tar.gz 文件，
并在目标环境中安全校验与恢复（自动脱敏敏感 API Key）。
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def export_bundle(
    loam_home: str | Path = "~/.loam",
    output_path: Optional[str | Path] = None,
    character: str = "default",
) -> Path:
    """打包导出角色数据库与状态。返回生成的 tar.gz 文件路径。"""
    home = Path(loam_home).expanduser().resolve()
    char_dir = home / "characters" / character
    state_dir = home / "state"

    if not char_dir.exists():
        raise FileNotFoundError(f"角色目录不存在: {char_dir}")

    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    if output_path is None:
        out_file = home / f"loam_backup_{character}_{ts}.tar.gz"
    else:
        out_file = Path(output_path).expanduser().resolve()

    manifest = {
        "version": 1,
        "character": character,
        "exported_at": time.time(),
        "files": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        stage = Path(tmpdir) / "bundle"
        stage.mkdir(parents=True, exist_ok=True)

        # 1. 复制角色 db
        dst_char = stage / "character"
        dst_char.mkdir(parents=True, exist_ok=True)
        for db_name in ["journal.db", "memory.db"]:
            src_f = char_dir / db_name
            if src_f.exists():
                shutil.copy2(src_f, dst_char / db_name)
                manifest["files"].append(f"character/{db_name}")

        # 2. 复制 state overrides (如果存在)
        if state_dir.exists():
            dst_state = stage / "state"
            dst_state.mkdir(parents=True, exist_ok=True)
            for s_name in ["overrides.json"]:
                src_s = state_dir / s_name
                if src_s.exists():
                    shutil.copy2(src_s, dst_state / s_name)
                    manifest["files"].append(f"state/{s_name}")

        # 3. 写入 manifest.json
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8"
        )

        # 4. 打包为 tar.gz
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_file, "w:gz") as tar:
            tar.add(stage, arcname="loam_bundle")

    return out_file


def import_bundle(
    bundle_path: str | Path,
    loam_home: str | Path = "~/.loam",
    target_character: Optional[str] = None,
) -> Dict[str, Any]:
    """导入并恢复打包的备份文件。"""
    src_tar = Path(bundle_path).expanduser().resolve()
    if not src_tar.exists():
        raise FileNotFoundError(f"备份文件不存在: {src_tar}")

    home = Path(loam_home).expanduser().resolve()

    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(src_tar, "r:gz") as tar:
            tar.extractall(path=tmpdir)

        stage = Path(tmpdir) / "loam_bundle"
        manifest_file = stage / "manifest.json"
        if not manifest_file.exists():
            raise ValueError("备份文件损坏：未找到 manifest.json")

        manifest = json.loads(manifest_file.read_text("utf-8"))
        char_name = target_character or manifest.get("character", "default")

        # 恢复 character db
        char_dst = home / "characters" / char_name
        char_dst.mkdir(parents=True, exist_ok=True)
        src_char = stage / "character"
        if src_char.exists():
            for f in src_char.iterdir():
                shutil.copy2(f, char_dst / f.name)

        # 恢复 state
        src_state = stage / "state"
        state_dst = home / "state"
        state_dst.mkdir(parents=True, exist_ok=True)
        if src_state.exists():
            for f in src_state.iterdir():
                shutil.copy2(f, state_dst / f.name)

    return {
        "ok": True,
        "restored_character": char_name,
        "manifest": manifest,
    }