#!/usr/bin/env python3
"""迁移一致性校验：对 manifest 中的行数/哈希做核对。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Sequence


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(path: Path) -> Dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest 不是对象")
    return data


def _verify_csv_hashes(manifest: Dict[str, object]) -> List[str]:
    errors: List[str] = []
    for art in manifest.get("artifacts", []):
        if not isinstance(art, dict):
            continue
        for t in art.get("tables", []):
            if not isinstance(t, dict):
                continue
            csv_path = Path(str(t.get("csv") or ""))
            expected = str(t.get("sha256") or "")
            if not csv_path.exists():
                errors.append(f"csv missing: {csv_path}")
                continue
            got = _sha256_file(csv_path)
            if expected and got != expected:
                errors.append(f"sha mismatch: {csv_path} expected={expected[:8]} got={got[:8]}")
    return errors


def _verify_sqlite_counts(manifest: Dict[str, object], db_override: Dict[str, Path]) -> List[str]:
    errors: List[str] = []
    for art in manifest.get("artifacts", []):
        if not isinstance(art, dict):
            continue
        name = str(art.get("name") or "")
        db_path = db_override.get(name)
        if db_path is None:
            db_path = Path(str(art.get("db") or ""))
        if not db_path.exists():
            errors.append(f"db missing for artifact={name}: {db_path}")
            continue

        conn = sqlite3.connect(str(db_path))
        try:
            for t in art.get("tables", []):
                if not isinstance(t, dict):
                    continue
                table = str(t.get("name") or "")
                expected = int(t.get("row_count") or 0)
                row = conn.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()
                got = int(row[0] if row else 0)
                if got != expected:
                    errors.append(
                        f"row_count mismatch db={name} table={table} expected={expected} got={got}"
                    )
        finally:
            conn.close()
    return errors


def _parse_db_override(raw: str) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    text = (raw or "").strip()
    if not text:
        return out
    for pair in text.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            continue
        out[k] = Path(v).expanduser().resolve()
    return out


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify migration manifest")
    p.add_argument("--manifest", required=True)
    p.add_argument(
        "--db-override",
        default="",
        help="override db path by artifact name, e.g. journal=/tmp/j.db,memory=/tmp/m.db",
    )
    args = p.parse_args(argv)

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    override = _parse_db_override(args.db_override)

    errors: List[str] = []
    errors.extend(_verify_csv_hashes(manifest))
    errors.extend(_verify_sqlite_counts(manifest, override))

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"ok": True, "checked_manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())