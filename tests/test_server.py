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