#!/usr/bin/env python3
"""冷热归档：把旧快照压缩为离线包（不删除主库）。"""

from __future__ import annotations

import argparse
import json
import tarfile
import time
from pathlib import Path
from typing import List, Sequence


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Archive old loam snapshots")
    p.add_argument("--snapshot-root", required=True)
    p.add_argument("--days-old", type=int, default=7)
    p.add_argument("--archive-dir", default="")
    args = p.parse_args(argv)

    root = Path(args.snapshot_root).expanduser().resolve()
    arc = Path(args.archive_dir).expanduser().resolve() if args.archive_dir else (root / "cold_archive")
    arc.mkdir(parents=True, exist_ok=True)

    cutoff = time.time() - max(1, int(args.days_old)) * 86400
    archived: List[str] = []
    skipped: List[str] = []

    for d in sorted(root.glob("snapshot_*")):
        if not d.is_dir():
            continue
        mtime = d.stat().st_mtime
        if mtime > cutoff:
            skipped.append(str(d))
            continue

        tar_path = arc / f"{d.name}.tar.gz"
        if tar_path.exists():
            skipped.append(str(d))
            continue

        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(d, arcname=d.name)
        archived.append(str(tar_path))

    print(
        json.dumps(
            {
                "ok": True,
                "snapshot_root": str(root),
                "archive_dir": str(arc),
                "archived": archived,
                "skipped": skipped,
                "note": "主库未删除；仅对快照目录做离线压缩归档。",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())