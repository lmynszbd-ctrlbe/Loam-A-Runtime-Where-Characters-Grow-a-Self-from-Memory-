#!/usr/bin/env python3
"""迁移回滚：从快照恢复 journal.db / memory.db。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rollback loam data files from snapshot")
    p.add_argument("--snapshot-dir", required=True, help="snapshot dir containing journal.db and memory.db")
    p.add_argument("--target-dir", required=True, help="character data dir")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    snap = Path(args.snapshot_dir).expanduser().resolve()
    tgt = Path(args.target_dir).expanduser().resolve()

    journal_src = snap / "journal.db"
    memory_src = snap / "memory.db"
    if not journal_src.exists() or not memory_src.exists():
        raise SystemExit(f"snapshot incomplete: {snap}")

    journal_dst = tgt / "journal.db"
    memory_dst = tgt / "memory.db"

    actions = [
        {"from": str(journal_src), "to": str(journal_dst)},
        {"from": str(memory_src), "to": str(memory_dst)},
    ]

    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "actions": actions}, ensure_ascii=False, indent=2))
        return 0

    tgt.mkdir(parents=True, exist_ok=True)
    shutil.copy2(journal_src, journal_dst)
    shutil.copy2(memory_src, memory_dst)

    print(json.dumps({"ok": True, "restored": actions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())