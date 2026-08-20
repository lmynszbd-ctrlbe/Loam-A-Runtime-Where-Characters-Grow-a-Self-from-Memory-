#!/usr/bin/env python3
"""把导出的迁移 SQL 实际加载到 Postgres/TiKV。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

try:
    from ._target_db import run_mysql_file, run_psql_file  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from _target_db import run_mysql_file, run_psql_file


def _load_manifest(path: Path) -> Dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest 不是对象")
    return data


def _collect_sql_paths(manifest: Dict[str, object], key: str) -> List[Path]:
    out: List[Path] = []
    for art in manifest.get("artifacts", []):
        if not isinstance(art, dict):
            continue
        p = str(art.get(key) or "").strip()
        if not p:
            continue
        out.append(Path(p).expanduser().resolve())
    return out


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load migration SQL into Postgres/TiKV")
    p.add_argument("--manifest", required=True)

    p.add_argument("--postgres-dsn", default="", help="Postgres DSN (postgresql://... or conn string)")
    p.add_argument("--postgres-bin", default="psql")
    p.add_argument("--skip-postgres", action="store_true")

    p.add_argument("--tikv-dsn", default="", help="TiKV/MySQL DSN, e.g. mysql://user:pass@host:4000/db")
    p.add_argument("--mysql-bin", default="mysql")
    p.add_argument("--skip-tikv", action="store_true")

    args = p.parse_args(argv)

    manifest = _load_manifest(Path(args.manifest).expanduser().resolve())
    pg_sqls = _collect_sql_paths(manifest, "postgres_sql")
    tk_sqls = _collect_sql_paths(manifest, "tikv_sql")

    loaded: Dict[str, List[str]] = {"postgres": [], "tikv": []}

    if not args.skip_postgres:
        if not args.postgres_dsn.strip():
            raise SystemExit("missing --postgres-dsn (or use --skip-postgres)")
        for sql_path in pg_sqls:
            run_psql_file(args.postgres_bin, args.postgres_dsn.strip(), sql_path)
            loaded["postgres"].append(str(sql_path))

    if not args.skip_tikv:
        if not args.tikv_dsn.strip():
            raise SystemExit("missing --tikv-dsn (or use --skip-tikv)")
        for sql_path in tk_sqls:
            run_mysql_file(args.mysql_bin, args.tikv_dsn.strip(), sql_path)
            loaded["tikv"].append(str(sql_path))

    print(
        json.dumps(
            {
                "ok": True,
                "manifest": args.manifest,
                "loaded": loaded,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())