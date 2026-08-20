#!/usr/bin/env python3
"""迁移目标库辅助：Postgres/TiKV(MySQL 协议) 命令构造与执行。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List
from urllib.parse import unquote, urlparse


def parse_mysql_dsn(dsn: str) -> Dict[str, str]:
    """解析 mysql://user:pass@host:3306/db 形式 DSN。"""
    u = urlparse(dsn)
    if u.scheme not in {"mysql", "tidb"}:
        raise ValueError("mysql dsn 必须以 mysql:// 或 tidb:// 开头")
    if not u.hostname or not u.path.strip("/"):
        raise ValueError("mysql dsn 至少要包含 host 与 db 名")
    return {
        "host": u.hostname,
        "port": str(u.port or 3306),
        "user": unquote(u.username or "root"),
        "password": unquote(u.password or ""),
        "database": unquote(u.path.lstrip("/")),
    }


def build_psql_cmd(psql_bin: str, dsn: str, sql_file: Path) -> List[str]:
    return [psql_bin, "-v", "ON_ERROR_STOP=1", "-d", dsn, "-f", str(sql_file)]


def build_mysql_base_cmd(mysql_bin: str, cfg: Dict[str, str]) -> List[str]:
    cmd = [
        mysql_bin,
        "--local-infile=1",
        "-h",
        cfg["host"],
        "-P",
        cfg["port"],
        "-u",
        cfg["user"],
        cfg["database"],
    ]
    pwd = cfg.get("password") or ""
    if pwd:
        cmd.append(f"-p{pwd}")
    return cmd


def run_psql_file(psql_bin: str, dsn: str, sql_file: Path) -> None:
    cmd = build_psql_cmd(psql_bin, dsn, sql_file)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "psql 执行失败\n"
            f"cmd={' '.join(cmd)}\n"
            f"stdout={r.stdout}\n"
            f"stderr={r.stderr}"
        )


def run_mysql_file(mysql_bin: str, dsn: str, sql_file: Path) -> None:
    cfg = parse_mysql_dsn(dsn)
    cmd = build_mysql_base_cmd(mysql_bin, cfg)
    with sql_file.open("rb") as f:
        r = subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "mysql 执行失败\n"
            f"cmd={' '.join(cmd)} < {sql_file}\n"
            f"stdout={r.stdout}\n"
            f"stderr={r.stderr}"
        )


def query_psql_scalar(psql_bin: str, dsn: str, sql: str) -> str:
    cmd = [psql_bin, "-At", "-d", dsn, "-c", sql]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "psql 查询失败\n"
            f"cmd={' '.join(cmd)}\n"
            f"stdout={r.stdout}\n"
            f"stderr={r.stderr}"
        )
    return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""


def query_mysql_scalar(mysql_bin: str, dsn: str, sql: str) -> str:
    cfg = parse_mysql_dsn(dsn)
    cmd = build_mysql_base_cmd(mysql_bin, cfg) + ["-Nse", sql]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "mysql 查询失败\n"
            f"cmd={' '.join(cmd)}\n"
            f"stdout={r.stdout}\n"
            f"stderr={r.stderr}"
        )
    return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""