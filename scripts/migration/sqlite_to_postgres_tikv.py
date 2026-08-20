#!/usr/bin/env python3
"""SQLite -> Postgres/TiKV 迁移导出脚本。

用途：
1) 从 loam 的 journal.db / memory.db 导出 CSV + schema。
2) 生成 Postgres 与 TiKV(MySQL 协议) 的建表/导入脚本。
3) 生成带行数与哈希的 manifest，供后续一致性校验。

说明：本脚本默认不直连目标库，保证离线可跑、可审计。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


@dataclass
class TableExport:
    name: str
    columns: List[str]
    row_count: int
    csv_path: str
    sha256: str
    sqlite_sql: str
    postgres_sql: str
    tikv_sql: str


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _mysql_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _map_type_pg(sqlite_type: str) -> str:
    t = (sqlite_type or "").strip().upper()
    if "INT" in t:
        return "BIGINT"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    if "BLOB" in t:
        return "BYTEA"
    if "BOOL" in t:
        return "BOOLEAN"
    return "TEXT"


def _map_type_tikv(sqlite_type: str) -> str:
    t = (sqlite_type or "").strip().upper()
    if "INT" in t:
        return "BIGINT"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE"
    if "BLOB" in t:
        return "LONGBLOB"
    if "BOOL" in t:
        return "TINYINT(1)"
    return "LONGTEXT"


def _list_tables(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    # FTS/虚拟表迁移由应用层重建，不在基础数据迁移里直接复制。
    # SQLite FTS5 还会生成一组 shadow tables（如 <fts>_data/_idx/_docsize/_config/_content），
    # 这些表同样属于可重建的派生索引，不应纳入基础迁移清单。
    virtual_tables = {
        str(r["name"])
        for r in rows
        if "VIRTUAL TABLE" in str(r["sql"] or "").upper()
    }

    out: List[sqlite3.Row] = []
    for r in rows:
        name = str(r["name"])
        sql = str(r["sql"] or "")
        if "VIRTUAL TABLE" in sql.upper():
            continue
        if any(name.startswith(vt + "_") for vt in virtual_tables):
            continue
        out.append(r)
    return out


def _column_info(conn: sqlite3.Connection, table: str) -> List[sqlite3.Row]:
    return conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()


def _export_table(conn: sqlite3.Connection, table: str, sqlite_sql: str, out_dir: Path) -> TableExport:
    cols_info = _column_info(conn, table)
    columns = [str(c["name"]) for c in cols_info]
    if not columns:
        raise RuntimeError(f"table has no columns: {table}")

    csv_path = out_dir / f"{table}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        rows = conn.execute(
            f"SELECT {', '.join(_quote_ident(c) for c in columns)} FROM {_quote_ident(table)}"
        )
        row_count = 0
        for row in rows:
            writer.writerow([row[c] for c in columns])
            row_count += 1

    pg_cols: List[str] = []
    tikv_cols: List[str] = []
    pk_cols = [str(c["name"]) for c in cols_info if int(c["pk"] or 0) > 0]
    for c in cols_info:
        name = str(c["name"])
        typ = str(c["type"] or "")
        nullable = int(c["notnull"] or 0) == 0

        pg_line = f"{_quote_ident(name)} {_map_type_pg(typ)}"

        tk_type = _map_type_tikv(typ)
        # MySQL/TiKV 不允许 TEXT/BLOB 直接做主键（需要前缀长度）。
        # 对文本/二进制主键列收敛到可索引的定长类型，避免 DDL 失败。
        if name in pk_cols:
            if tk_type == "LONGTEXT":
                tk_type = "VARCHAR(191)"
            elif tk_type == "LONGBLOB":
                tk_type = "VARBINARY(191)"
        tk_line = f"{_mysql_ident(name)} {tk_type}"

        if not nullable:
            pg_line += " NOT NULL"
            tk_line += " NOT NULL"
        pg_cols.append(pg_line)
        tikv_cols.append(tk_line)

    if pk_cols:
        pg_cols.append("PRIMARY KEY (" + ", ".join(_quote_ident(x) for x in pk_cols) + ")")
        tikv_cols.append("PRIMARY KEY (" + ", ".join(_mysql_ident(x) for x in pk_cols) + ")")

    postgres_sql = (
        f"CREATE TABLE IF NOT EXISTS {_quote_ident(table)} (\n  "
        + ",\n  ".join(pg_cols)
        + "\n);"
    )
    tikv_sql = (
        f"CREATE TABLE IF NOT EXISTS {_mysql_ident(table)} (\n  "
        + ",\n  ".join(tikv_cols)
        + "\n) ENGINE=InnoDB;"
    )

    return TableExport(
        name=table,
        columns=columns,
        row_count=row_count,
        csv_path=str(csv_path),
        sha256=_sha256_file(csv_path),
        sqlite_sql=sqlite_sql,
        postgres_sql=postgres_sql,
        tikv_sql=tikv_sql,
    )


def _export_one_db(db_path: Path, out_root: Path) -> Dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        db_out = out_root / db_path.stem
        db_out.mkdir(parents=True, exist_ok=True)

        exports: List[TableExport] = []
        for row in _list_tables(conn):
            exports.append(
                _export_table(
                    conn,
                    table=str(row["name"]),
                    sqlite_sql=str(row["sql"] or ""),
                    out_dir=db_out,
                )
            )

        pg_sql_path = db_out / "postgres_load.sql"
        tk_sql_path = db_out / "tikv_load.sql"

        pg_lines: List[str] = ["-- generated by sqlite_to_postgres_tikv.py"]
        tk_lines: List[str] = ["-- generated by sqlite_to_postgres_tikv.py"]
        for e in exports:
            pg_lines.append(e.postgres_sql)
            pg_lines.append(
                "\\copy "
                + _quote_ident(e.name)
                + " ("
                + ", ".join(_quote_ident(c) for c in e.columns)
                + ") FROM '"
                + Path(e.csv_path).as_posix()
                + "' WITH (FORMAT csv, HEADER true);"
            )

            tk_lines.append(e.tikv_sql)
            tk_lines.append(
                "LOAD DATA LOCAL INFILE '"
                + Path(e.csv_path).as_posix()
                + "' INTO TABLE "
                + _mysql_ident(e.name)
                + " FIELDS TERMINATED BY ',' ENCLOSED BY '\"'"

                + " LINES TERMINATED BY '\\n' IGNORE 1 LINES ("
                + ", ".join(_mysql_ident(c) for c in e.columns)
                + ");"
            )

        pg_sql_path.write_text("\n\n".join(pg_lines) + "\n", encoding="utf-8")
        tk_sql_path.write_text("\n\n".join(tk_lines) + "\n", encoding="utf-8")

        return {
            "db": str(db_path),
            "name": db_path.stem,
            "tables": [
                {
                    "name": e.name,
                    "row_count": e.row_count,
                    "columns": e.columns,
                    "csv": e.csv_path,
                    "sha256": e.sha256,
                }
                for e in exports
            ],
            "postgres_sql": str(pg_sql_path),
            "tikv_sql": str(tk_sql_path),
        }
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export SQLite to Postgres/TiKV migration artifacts")
    p.add_argument("--journal-db", required=True, help="path to journal.db")
    p.add_argument("--memory-db", required=True, help="path to memory.db")
    p.add_argument("--out-dir", required=True, help="output directory")
    p.add_argument("--label", default="", help="optional label in manifest")
    args = p.parse_args(argv)

    journal_db = Path(args.journal_db).expanduser().resolve()
    memory_db = Path(args.memory_db).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "label": args.label,
        "generated_at": __import__("time").time(),
        "artifacts": [
            _export_one_db(journal_db, out_dir),
            _export_one_db(memory_db, out_dir),
        ],
    }

    manifest = out_dir / "migration_manifest.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "manifest": str(manifest), "out_dir": str(out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())