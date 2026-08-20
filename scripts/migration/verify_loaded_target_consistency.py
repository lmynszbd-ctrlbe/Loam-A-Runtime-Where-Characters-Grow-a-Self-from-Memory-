#!/usr/bin/env python3
"""校验目标库（Postgres/TiKV）与 manifest 的行数一致性。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

try:
    from ._target_db import query_mysql_scalar, query_psql_scalar  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from _target_db import query_mysql_scalar, query_psql_scalar


def _load_manifest(path: Path) -> Dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest 不是对象")
    return data


def _tables(manifest: Dict[str, object]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for art in manifest.get("artifacts", []):
        if not isinstance(art, dict):
            continue
        db_name = str(art.get("name") or "")
        for t in art.get("tables", []):
            if not isinstance(t, dict):
                continue
            out.append(
                {
                    "artifact": db_name,
                    "table": str(t.get("name") or ""),
                    "row_count": int(t.get("row_count") or 0),
                }
            )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify loaded target DB row counts")
    p.add_argument("--manifest", required=True)
    p.add_argument("--target", choices=["postgres", "tikv"], required=True)
    p.add_argument("--postgres-dsn", default="")
    p.add_argument("--tikv-dsn", default="")
    p.add_argument("--postgres-bin", default="psql")
    p.add_argument("--mysql-bin", default="mysql")
    args = p.parse_args(argv)

    manifest = _load_manifest(Path(args.manifest).expanduser().resolve())
    rows = _tables(manifest)

    errors: List[str] = []
    checked: List[Dict[str, object]] = []

    if args.target == "postgres":
        if not args.postgres_dsn.strip():
            raise SystemExit("missing --postgres-dsn")
        for r in rows:
            table = str(r["table"]) or ""
            expected = int(r["row_count"])
            sql = f'SELECT COUNT(*) FROM "{table}";'
            got = int(query_psql_scalar(args.postgres_bin, args.postgres_dsn.strip(), sql) or 0)
            checked.append({"table": table, "expected": expected, "got": got})
            if got != expected:
                errors.append(f"table={table} expected={expected} got={got}")

    if args.target == "tikv":
        if not args.tikv_dsn.strip():
            raise SystemExit("missing --tikv-dsn")
        for r in rows:
            table = str(r["table"]) or ""
            expected = int(r["row_count"])
            sql = f"SELECT COUNT(*) FROM `{table}`;"
            got = int(query_mysql_scalar(args.mysql_bin, args.tikv_dsn.strip(), sql) or 0)
            checked.append({"table": table, "expected": expected, "got": got})
            if got != expected:
                errors.append(f"table={table} expected={expected} got={got}")

    out = {
        "ok": not errors,
        "target": args.target,
        "checked": checked,
        "errors": errors,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())