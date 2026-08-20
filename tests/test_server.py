"""HTTP 服务测试。"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.mind.llm import ScriptedBrain
from loam.server import LoamService, ServiceConfig, build_server


def _start_service(api_key: str = ""):
    tmp = tempfile.mkdtemp()
    brain = ScriptedBrain(
        [
            [
                {
                    "summary": "对方说明天开会有点紧张",
                    "questions": ["对方为什么紧张"],
                    "entities": ["开会"],
                    "salience": 0.6,
                    "valence": -0.2,
                    "stood_firm": False,
                    "source_turns": [1],
                }
            ],
            {"appraisals": [], "proposals": []},
            [],
        ]
    )
    svc = LoamService(
        ServiceConfig(
            character="阿萤",
            home=tmp,
            auto_start_grower=False,
            batch_turns=20,
            audit_every=0,
            api_key=api_key,
        ),
        brain=brain,
    )
    httpd = build_server(svc, host="127.0.0.1", port=0)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return tmp, svc, httpd, th


def _stop_service(tmp: str, svc: LoamService, httpd):
    httpd.shutdown()
    httpd.server_close()
    svc.close()
    shutil.rmtree(tmp)


def _req(base: str, method: str, path: str, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    hs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hs.update(headers)
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers=hs,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def test_health_and_stats_endpoint():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        s1, j1 = _req(base, "GET", "/health")
        s2, j2 = _req(base, "GET", "/stats")

        assert s1 == 200 and j1["ok"] is True
        assert s2 == 200 and j2["character"] == "阿萤"
        assert "journal" in j2 and "memory" in j2
    finally:
        _stop_service(tmp, svc, httpd)


def test_ingest_then_digest_endpoint():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        s1, j1 = _req(
            base,
            "POST",
            "/ingest",
            {
                "session": "s1",
                "turns": [
                    {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
                    {"turn": 1, "role": "assistant", "content": "我们来准备一下"},
                ],
            },
        )
        assert s1 == 200
        assert j1["added"] == 2

        s2, j2 = _req(base, "POST", "/digest", {})
        assert s2 == 200
        assert j2["新事件"] == 1, j2
        assert j2["pending"] == 0
    finally:
        _stop_service(tmp, svc, httpd)


def test_context_endpoint_returns_rendered_text():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        _req(
            base,
            "POST",
            "/ingest",
            {
                "session": "s1",
                "turns": [
                    {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
                    {"turn": 1, "role": "assistant", "content": "我们来准备一下"},
                ],
            },
        )
        _req(base, "POST", "/digest", {})

        s, data = _req(base, "POST", "/context", {"query": "明天开会", "learn": False})
        assert s == 200
        assert "text" in data and "context" in data
        assert "被想起的经历" in data["text"]
        assert data["context"]["recalled"], "应返回至少一条相关记忆"
    finally:
        _stop_service(tmp, svc, httpd)


def test_api_key_protects_non_health_routes():
    tmp, svc, httpd, _ = _start_service(api_key="secret-token")
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        # 健康探针允许匿名
        s0, j0 = _req(base, "GET", "/health")
        assert s0 == 200 and j0["ok"] is True

        s1, _ = _req(base, "GET", "/stats")
        assert s1 == 401

        s2, j2 = _req(base, "GET", "/stats", headers={"X-API-Key": "secret-token"})
        assert s2 == 200
        assert j2["character"] == "阿萤"
    finally:
        _stop_service(tmp, svc, httpd)


def test_runtime_config_dashboard_and_explain_endpoints():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        s0, dashboard0 = _req(base, "GET", "/dashboard")
        assert s0 == 200
        assert dashboard0["alerts"]["level"] in {"info", "warn", "error"}
        assert "metrics" in dashboard0 and "dialog" in dashboard0["metrics"]
        assert "windows" in dashboard0 and "events" in dashboard0["windows"]
        assert "decay" in dashboard0

        s1, cfg1 = _req(base, "GET", "/config")
        assert s1 == 200
        assert cfg1["current"]["context.max_matches"] == 8

        s2, upd = _req(
            base,
            "POST",
            "/config/update",
            {
                "updates": {
                    "context.max_matches": 6,
                    "ingest.max_turns_per_request": 2,
                },
                "note": "test update",
            },
        )
        assert s2 == 200
        assert upd["current"]["context.max_matches"] == 6
        assert upd["current"]["ingest.max_turns_per_request"] == 2

        # 触发一轮 ingest+digest，确保 explain 有内容可查。
        _req(
            base,
            "POST",
            "/ingest",
            {
                "session": "s1",
                "turns": [
                    {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
                    {"turn": 2, "role": "assistant", "content": "好的"},
                    {"turn": 3, "role": "assistant", "content": "好的"},
                ],
            },
        )
        _req(base, "POST", "/digest", {})

        s3, ex = _req(base, "GET", "/explain?limit=10")
        assert s3 == 200
        assert "items" in ex and isinstance(ex["items"], list)

        s4, cfg2 = _req(base, "GET", "/config")
        assert s4 == 200
        target_version = None
        for item in cfg2.get("history", []):
            conf = item.get("config") or {}
            if conf.get("context.max_matches") == 8:
                target_version = int(item["id"])
                break
        assert target_version is not None

        s5, rb = _req(base, "POST", "/config/rollback", {"version": target_version, "note": "rollback"})
        assert s5 == 200
        assert rb["current"]["context.max_matches"] == 8
    finally:
        _stop_service(tmp, svc, httpd)


def test_ingest_prefilter_drops_smalltalk_and_duplicates():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        s, data = _req(
            base,
            "POST",
            "/ingest",
            {
                "session": "s_prefilter",
                "turns": [
                    {"turn": 1, "role": "user", "content": "你好"},
                    {"turn": 2, "role": "user", "content": "你好"},
                    {"turn": 3, "role": "assistant", "content": "好的"},
                    {"turn": 4, "role": "assistant", "content": "好的"},
                    {"turn": 5, "role": "user", "content": "我明天要开会"},
                ],
            },
        )
        assert s == 200
        assert data["added"] == 1, data
        assert data["dropped_lightweight"] >= 4, data
    finally:
        _stop_service(tmp, svc, httpd)


def test_recompute_and_experiment_endpoints():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        s0, _ = _req(
            base,
            "POST",
            "/config/update",
            {
                "updates": {
                    "decay.enabled": True,
                    "decay.half_life_hours": 12,
                    "dashboard.window_seconds": 7200,
                },
                "note": "experiment tweak",
            },
        )
        assert s0 == 200

        s1, exps = _req(base, "GET", "/experiments?limit=5")
        assert s1 == 200
        assert exps["items"], exps

        s2, rec = _req(base, "POST", "/recompute", {"mode": "incremental", "note": "test"})
        assert s2 == 200
        assert rec["ok"] is True

        s3, hist = _req(base, "GET", "/recompute/history?limit=3")
        assert s3 == 200
        assert hist["items"], hist
        assert hist["items"][0]["mode"] == "incremental"
    finally:
        _stop_service(tmp, svc, httpd)


def test_unknown_route_returns_404_json():
    tmp, svc, httpd, _ = _start_service()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        s, data = _req(base, "GET", "/nope")
        assert s == 404
        assert "error" in data
    finally:
        _stop_service(tmp, svc, httpd)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)