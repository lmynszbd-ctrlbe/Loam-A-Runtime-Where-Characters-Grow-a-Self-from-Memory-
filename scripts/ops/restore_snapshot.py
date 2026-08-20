#!/usr/bin/env python3
"""从快照目录恢复 loam 数据文件。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Restore loam snapshot")
    p.add_argument("--snapshot-dir", required=True)
    p.add_argument("--character-dir", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    snap = Path(args.snapshot_dir).expanduser().resolve()
    dst = Path(args.character_dir).expanduser().resolve()

    files = ["journal.db", "memory.db"]
    actions = []
    for name in files:
        src = snap / name
        if not src.exists():
            continue
        actions.append({"from": str(src), "to": str(dst / name)})

    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "actions": actions}, ensure_ascii=False, indent=2))
        return 0

    dst.mkdir(parents=True, exist_ok=True)
    for a in actions:
        shutil.copy2(Path(a["from"]), Path(a["to"]))

    print(json.dumps({"ok": True, "restored": actions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())