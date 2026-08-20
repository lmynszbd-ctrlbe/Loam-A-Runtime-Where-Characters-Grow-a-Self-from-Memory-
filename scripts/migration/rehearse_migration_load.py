#!/usr/bin/env python3
"""迁移压测演练流程：重复执行导出+校验，输出耗时分布。"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from statistics import mean
from typing import List, Sequence


def _run(cmd: List[str]) -> None:
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\nstdout={r.stdout}\nstderr={r.stderr}")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rehearse SQLite->Postgres/TiKV migration")
    p.add_argument("--journal-db", required=True)
    p.add_argument("--memory-db", required=True)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--work-dir", default="")
    args = p.parse_args(argv)

    rounds = max(1, int(args.rounds))
    root = Path(args.work_dir).expanduser().resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="loam_mig_"))
    root.mkdir(parents=True, exist_ok=True)

    export_py = Path(__file__).with_name("sqlite_to_postgres_tikv.py")
    verify_py = Path(__file__).with_name("verify_migration_consistency.py")

    costs: List[float] = []
    manifests: List[str] = []
    for i in range(1, rounds + 1):
        out_dir = root / f"round_{i}"
        t0 = time.time()
        _run(
            [
                "python",
                str(export_py),
                "--journal-db",
                str(Path(args.journal_db).expanduser().resolve()),
                "--memory-db",
                str(Path(args.memory_db).expanduser().resolve()),
                "--out-dir",
                str(out_dir),
                "--label",
                f"rehearsal-round-{i}",
            ]
        )
        manifest = out_dir / "migration_manifest.json"
        _run(["python", str(verify_py), "--manifest", str(manifest)])
        elapsed = time.time() - t0
        costs.append(elapsed)
        manifests.append(str(manifest))

    report = {
        "ok": True,
        "rounds": rounds,
        "avg_seconds": round(mean(costs), 3),
        "max_seconds": round(max(costs), 3),
        "min_seconds": round(min(costs), 3),
        "durations": [round(x, 3) for x in costs],
        "manifests": manifests,
        "work_dir": str(root),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())