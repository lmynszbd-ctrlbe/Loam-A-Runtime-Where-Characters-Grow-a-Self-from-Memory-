"""集成测试：从 ingest 到 digest/context 的端到端链路。"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.mind import prompts
from loam.mind.llm import Brain, BrainError, ScriptedBrain
from loam.server import LoamService, ServiceConfig, build_server


def _ids_in(prompt: str) -> List[str]:
    return re.findall(r"\[(ev_[0-9_]+)\]", prompt)


class MiniPhasedBrain(ScriptedBrain):
    """按步骤回答的稳定测试脑子（不会耗尽剧本）。"""

    def __init__(self) -> None:
        super().__init__([])

    def ask(self, system: str, user: str, **kw: Any) -> str:  # type: ignore[override]
        self.asked.append(user)
        self.usage.add(len(user) // 4, 64)

        if system == prompts.EXTRACT_SYSTEM:
            out = [
                {
                    "summary": "对方说明天要开会，心里有点紧张",
                    "questions": ["对方最近为什么紧张"],
                    "entities": ["开会"],
                    "salience": 0.6,
                    "valence": -0.2,
                    "stood_firm": False,
                    "source_turns": [1],
                },
                {
                    "summary": "角色没有顺着安抚，而是建议先做准备",
                    "questions": ["角色会不会只说好听话"],
                    "entities": ["准备"],
                    "salience": 0.5,
                    "valence": 0.2,
                    "stood_firm": True,
                    "source_turns": [2],
                },
            ]
            return json.dumps(out, ensure_ascii=False)

        if system == prompts.APPRAISE_SYSTEM:
            ids = _ids_in(user)
            out = {
                "appraisals": [],
                "proposals": [
                    {
                        "text": "我倾向于先把事情拆开准备，而不是只给安慰",
                        "event_ids": ids[:2],
                        "why": "多次出现这种选择",
                    }
                ],
            }
            return json.dumps(out, ensure_ascii=False)

        if system == prompts.OBSERVE_SYSTEM:
            return "[]"

        if system == prompts.DOSSIER_SYSTEM:
            ids = _ids_in(user)
            out = [
                {
                    "key": "近期主题",
                    "value": "对方在为开会做准备",
                    "event_ids": ids[:1],
                    "confidence": 0.85,
                }
            ]
            return json.dumps(out, ensure_ascii=False)

        if system == prompts.NARRATE_SYSTEM:
            return "我大概是那种会先把事拆开，再决定怎么说的人。"

        if system == prompts.DRIFT_SYSTEM:
            return json.dumps({"lost": [], "drifted": [], "severity": 0.0, "note": "无"}, ensure_ascii=False)

        raise BrainError("未知步骤")


def _feed_basic(service: LoamService) -> Dict[str, Any]:
    return service.ingest(
        {
            "session": "s1",
            "turns": [
                {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
                {"turn": 1, "role": "assistant", "content": "我们先把要点列出来"},
                {"turn": 2, "role": "user", "content": "我怕到时候脑子空白"},
                {"turn": 2, "role": "assistant", "content": "那先做两轮演练"},
            ],
        }
    )


def test_e2e_service_pipeline():
    tmp = tempfile.mkdtemp()
    try:
        svc = LoamService(
            ServiceConfig(character="阿萤", home=tmp, auto_start_grower=False, audit_every=0),
            brain=MiniPhasedBrain(),
        )

        ing = _feed_basic(svc)
        assert ing["added"] == 4
        assert ing["pending"] == 4

        rep = svc.digest_once()
        assert rep["新事件"] == 2, rep
        assert rep["pending"] == 0

        ctx = svc.build_context("明天开会", learn=False)
        assert "被想起的经历" in ctx["text"]
        assert ctx["context"]["recalled"], "应该召回至少一条记忆"

        st = svc.stats()
        assert st["memory"]["事件"] >= 2
        assert st["journal"]["待消化"] == 0
    finally:
        svc.close()
        shutil.rmtree(tmp)


def test_e2e_background_grower_autonomous():
    tmp = tempfile.mkdtemp()
    try:
        svc = LoamService(
            ServiceConfig(
                character="阿萤",
                home=tmp,
                auto_start_grower=True,
                grow_interval=0.05,
                idle_seconds=0.0,
                audit_every=0,
            ),
            brain=MiniPhasedBrain(),
        )
        _feed_basic(svc)

        deadline = time.time() + 5.0
        while time.time() < deadline and svc.digester.pending_count() > 0:
            time.sleep(0.05)

        assert svc.digester.pending_count() == 0, "后台线程应自动吃掉生料"
        assert svc.memory.stats()["事件"] >= 1
        assert svc.grower.alive
    finally:
        svc.close()
        shutil.rmtree(tmp)


def _http_req(base: str, method: str, path: str, body: Dict[str, Any] | None = None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        method=method,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, (json.loads(raw) if raw else {})


def test_e2e_http_roundtrip():
    tmp = tempfile.mkdtemp()
    try:
        svc = LoamService(
            ServiceConfig(character="阿萤", home=tmp, auto_start_grower=False, audit_every=0),
            brain=MiniPhasedBrain(),
        )
        httpd = build_server(svc, host="127.0.0.1", port=0)
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()

        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        s1, j1 = _http_req(base, "POST", "/ingest", _feed_payload())
        assert s1 == 200 and j1["added"] == 4

        s2, j2 = _http_req(base, "POST", "/drain", {"max_rounds": 10})
        assert s2 == 200
        assert j2["pending"] == 0
        assert j2["rounds"] >= 1

        q = quote("明天开会")
        s3, j3 = _http_req(base, "GET", f"/context?q={q}&learn=0")
        assert s3 == 200
        assert "text" in j3 and "被想起的经历" in j3["text"]
    finally:
        httpd.shutdown()
        httpd.server_close()
        svc.close()
        shutil.rmtree(tmp)


def test_no_key_degrades_without_losing_raw():
    """没配后台脑子时，digest 必须失败但生料不能丢。"""
    tmp = tempfile.mkdtemp()
    try:
        svc = LoamService(
            ServiceConfig(character="阿萤", home=tmp, auto_start_grower=False, audit_every=0),
            brain=Brain(api_key=""),
        )
        _feed_basic(svc)
        before = svc.digester.pending_count()

        rep = svc.digest_once()
        assert rep["出错"], "应该报没配脑子"
        assert svc.digester.pending_count() == before, "失败后生料必须还在"
        assert svc.memory.stats()["事件"] == 0
    finally:
        svc.close()
        shutil.rmtree(tmp)


def _feed_payload() -> Dict[str, Any]:
    return {
        "session": "s1",
        "turns": [
            {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
            {"turn": 1, "role": "assistant", "content": "我们先把要点列出来"},
            {"turn": 2, "role": "user", "content": "我怕到时候脑子空白"},
            {"turn": 2, "role": "assistant", "content": "那先做两轮演练"},
        ],
    }


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