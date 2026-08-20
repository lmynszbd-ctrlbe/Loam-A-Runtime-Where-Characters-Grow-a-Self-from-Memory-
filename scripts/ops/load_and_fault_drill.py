#!/usr/bin/env python3
"""压测 + 故障演练脚本（HTTP）。"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Sequence, Tuple


def _req(base: str, method: str, path: str, body: Dict[str, Any] | None = None) -> Tuple[int, Dict[str, Any]]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def _feed_session(base: str, session: str, turns: int, out: List[Dict[str, Any]]) -> None:
    payload = {
        "session": session,
        "turns": [
            {"turn": i, "role": "user", "content": f"{session} 第{i}轮：我在准备发布"}
            for i in range(1, turns + 1)
        ],
    }
    st, data = _req(base, "POST", "/ingest", payload)
    out.append({"session": session, "status": st, "added": data.get("added", 0), "error": data.get("error")})


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="loam load & fault drill")
    p.add_argument("--base-url", required=True)
    p.add_argument("--sessions", type=int, default=5)
    p.add_argument("--turns", type=int, default=40)
    p.add_argument("--fault-check", action="store_true")
    args = p.parse_args(argv)

    base = args.base_url
    sessions = max(1, int(args.sessions))
    turns = max(1, int(args.turns))

    ingest_results: List[Dict[str, Any]] = []
    threads: List[threading.Thread] = []
    t0 = time.time()
    for i in range(1, sessions + 1):
        th = threading.Thread(target=_feed_session, args=(base, f"load_s{i}", turns, ingest_results), daemon=True)
        threads.append(th)
        th.start()

    for th in threads:
        th.join()

    st_drain, drain = _req(base, "POST", "/drain", {"max_rounds": sessions * 3})
    st_dashboard, dashboard = _req(base, "GET", "/dashboard")

    faults: List[Dict[str, Any]] = []
    if args.fault_check:
        # 故障注入 1：非法配置项，期望 400
        s_bad_cfg, j_bad_cfg = _req(base, "POST", "/config/update", {"updates": {"bad.key": 1}})
        faults.append({"case": "invalid_config", "status": s_bad_cfg, "body": j_bad_cfg})

        # 故障注入 2：空 ingest，期望 400
        s_bad_ing, j_bad_ing = _req(base, "POST", "/ingest", {"session": "fault", "turns": []})
        faults.append({"case": "empty_ingest", "status": s_bad_ing, "body": j_bad_ing})

    report = {
        "ok": True,
        "elapsed_seconds": round(time.time() - t0, 3),
        "sessions": sessions,
        "turns_per_session": turns,
        "ingest_results": ingest_results,
        "drain_status": st_drain,
        "drain": drain,
        "dashboard_status": st_dashboard,
        "backlog": (dashboard.get("backlog") if isinstance(dashboard, dict) else None),
        "faults": faults,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())