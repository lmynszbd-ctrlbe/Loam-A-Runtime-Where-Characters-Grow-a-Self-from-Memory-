#!/usr/bin/env python3
"""创建 loam 数据快照（用于备份、恢复、迁移回滚）。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Dict, Sequence


FILES = ("journal.db", "memory.db")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Create loam snapshot")
    p.add_argument("--character-dir", required=True)
    p.add_argument("--out-dir", required=True)
    args = p.parse_args(argv)

    src = Path(args.character_dir).expanduser().resolve()
    out_root = Path(args.out_dir).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    dst = out_root / f"snapshot_{stamp}"
    dst.mkdir(parents=True, exist_ok=True)

    hashes: Dict[str, str] = {}
    copied: Dict[str, str] = {}
    for name in FILES:
        s = src / name
        if not s.exists():
            continue
        d = dst / name
        shutil.copy2(s, d)
        hashes[name] = _sha256(d)
        copied[name] = str(d)

    meta = {
        "ok": True,
        "created_at": time.time(),
        "source": str(src),
        "snapshot_dir": str(dst),
        "files": copied,
        "sha256": hashes,
    }
    (dst / "snapshot_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())