"""loam 本地 HTTP 服务。

原则：
- 纯标准库，可在云机/本机/Termux 直接跑。
- API 很薄：收料、消化、拿上下文、看状态。
- 进程内自带后台成长线程（可开可关）。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .mind.context import ContextBuilder
from .mind.digest import Digester, Grower
from .mind.llm import Brain, load_brain
from .store.journal import Journal
from .store.memory import Memory


@dataclass
class ServiceConfig:
    character: str = "default"
    home: str = "~/.loam/characters"
    default_session: str = "default"
    batch_turns: int = 20
    grow_interval: float = 60.0
    idle_seconds: float = 900.0
    audit_every: int = 50
    auto_start_grower: bool = True
    api_key: str = ""


class LoamService:
    """进程内核心服务。HTTP 和 CLI 都调它。"""

    def __init__(self, config: ServiceConfig, brain: Optional[Brain] = None) -> None:
        self.config = config
        self.character = config.character
        self.root = Path(config.home).expanduser() / self.character
        self.root.mkdir(parents=True, exist_ok=True)

        self.journal = Journal(self.root / "journal.db")
        self.memory = Memory(self.root / "memory.db")
        self.brain = brain or load_brain()
        self.api_key = (config.api_key or os.environ.get("LOAM_API_KEY", "")).strip()

        # 崩溃恢复：把遗留 processing 队列任务恢复为 pending。
        self.journal.recover_processing_jobs(self.character)

        self.digester = Digester(
            self.character,
            self.journal,
            self.memory,
            self.brain,
            batch_turns=config.batch_turns,
        )
        self.context = ContextBuilder(self.memory)

        # 所有 journal/memory 操作都走同一把锁，避免 HTTP 请求与后台 grower 竞态。
        self._lock = threading.RLock()

        self.grower = Grower(
            self.digester,
            interval=config.grow_interval,
            idle_seconds=config.idle_seconds,
            audit_every=config.audit_every,
            step_lock=self._lock,
        )

        if config.auto_start_grower:
            self.grower.start()

    # ------------------------------------------------------------ 输入

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """写入一批原始证据到 pending 队列。"""
        session = str(payload.get("session") or self.config.default_session)
        turns = _normalise_turns(payload)
        if not turns:
            raise ValueError("ingest 需要 turns/messages 或 (turn, role, content)")

        with self._lock:
            seen_turns = sorted({int(t["turn"]) for t in turns})
            gaps: List[Dict[str, int]] = []
            for t in seen_turns:
                gap = self.journal.observe_turn(self.character, session, t)
                if gap:
                    gaps.append({"from": int(gap[0]), "to": int(gap[1])})

            filtered_turns, dropped = _prefilter_evidence(turns)
            if filtered_turns:
                queued = self.journal.enqueue_pending_evidence(
                    self.character,
                    session,
                    filtered_turns,
                    client=str(payload.get("client")) if payload.get("client") else None,
                    model=str(payload.get("model")) if payload.get("model") else None,
                )
            else:
                qstats0 = self.journal.queue_stats(self.character)
                queued = {
                    "added": 0,
                    "deduped": 0,
                    "pending_evidence": int(qstats0.get("pending_evidence", 0)),
                    "jobs_pending": int(qstats0.get("jobs_pending", 0)),
                    "jobs_processing": int(qstats0.get("jobs_processing", 0)),
                }

            queue_now: Dict[str, int] = {}
            # 可选同步模式：本次请求内先处理一轮队列
            if _coerce_bool(payload.get("sync"), default=False):
                queue_now = self.journal.drain_ingest_jobs(self.character, max_jobs=1)

            qstats = self.journal.queue_stats(self.character)
            return {
                "character": self.character,
                "session": session,
                "added": int(queued.get("added") or 0),
                "deduped": int(queued.get("deduped") or 0),
                "dropped_lightweight": dropped,
                "turns": seen_turns,
                "gaps": gaps,
                "open_gaps": self.journal.open_gaps(self.character),
                "pending": self.digester.pending_count(),
                "pending_evidence": int(qstats.get("pending_evidence", 0)),
                "queue": qstats,
                "queue_now": queue_now,
            }

    # ------------------------------------------------------------ 处理

    def digest_once(self, limit: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            queue_now = self.journal.drain_ingest_jobs(self.character, max_jobs=1)
            report = self.digester.digest_once(limit=limit)
            out = report.as_dict()
            out["pending"] = self.digester.pending_count()
            out["queue"] = self.journal.queue_stats(self.character)
            out["queue_now"] = queue_now
            return out

    def drain(self, max_rounds: int = 50) -> Dict[str, Any]:
        with self._lock:
            queue_now = self.journal.drain_ingest_jobs(self.character, max_jobs=max_rounds)
            reports = self.grower.drain(max_rounds=max_rounds)
            return {
                "rounds": len(reports),
                "reports": [r.as_dict() for r in reports],
                "pending": self.digester.pending_count(),
                "queue": self.journal.queue_stats(self.character),
                "queue_now": queue_now,
            }

    # ------------------------------------------------------------ 输出

    def build_context(self, query: str, learn: bool = False) -> Dict[str, Any]:
        with self._lock:
            pack = self.context.build(self.character, query=query, learn=learn)
            return {"context": pack.as_dict(), "text": pack.render()}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "character": self.character,
                "root": str(self.root),
                "journal": self.journal.stats(self.character),
                "memory": self.memory.stats(),
                "pending": self.digester.pending_count(),
                "grower_alive": self.grower.alive,
                "last_error": self.grower.last_error,
            }

    def healthz(self) -> Dict[str, Any]:
        with self._lock:
            pending = self.digester.pending_count()
            ok = True
            if self.config.auto_start_grower and not self.grower.alive:
                ok = False
            return {
                "ok": ok,
                "character": self.character,
                "pending": pending,
                "open_gaps": len(self.journal.open_gaps(self.character)),
                "grower_alive": self.grower.alive,
                "last_error": self.grower.last_error,
                "ts": time.time(),
            }

    # ------------------------------------------------------------ grower

    def start_grower(self) -> Dict[str, Any]:
        self.grower.start()
        return {"grower_alive": self.grower.alive}

    def stop_grower(self) -> Dict[str, Any]:
        self.grower.stop()
        return {"grower_alive": self.grower.alive}

    # ------------------------------------------------------------ 生命周期

    def close(self) -> None:
        self.grower.stop()
        self.journal.close()
        self.memory.close()


class LoamHTTPServer(ThreadingHTTPServer):
    """把 service 挂在 server 上，handler 里直接拿。"""

    def __init__(self, server_address: tuple[str, int], service: LoamService):
        self.service = service
        super().__init__(server_address, LoamHandler)


class LoamHandler(BaseHTTPRequestHandler):
    server: LoamHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._send_json(200, {"ok": True, "character": self.server.service.character})
                return

            if not self._require_auth(path):
                return

            if path == "/healthz":
                self._send_json(200, self.server.service.healthz())
                return

            if path == "/stats":
                self._send_json(200, self.server.service.stats())
                return

            if path == "/context":
                query = (qs.get("q") or [""])[0]
                learn = _coerce_bool((qs.get("learn") or [None])[0], default=False)
                self._send_json(200, self.server.service.build_context(query, learn=learn))
                return

            self._send_json(404, {"error": f"unknown route: {path}"})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_internal_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if not self._require_auth(path):
                return

            payload = self._read_json()

            if path == "/ingest":
                self._send_json(200, self.server.service.ingest(payload))
                return

            if path == "/digest":
                limit = payload.get("limit")
                self._send_json(200, self.server.service.digest_once(limit=int(limit) if limit else None))
                return

            if path == "/drain":
                rounds = int(payload.get("max_rounds") or 50)
                self._send_json(200, self.server.service.drain(max_rounds=rounds))
                return

            if path == "/context":
                query = str(payload.get("query") or "")
                learn = _coerce_bool(payload.get("learn"), default=False)
                self._send_json(200, self.server.service.build_context(query, learn=learn))
                return

            if path == "/grower/start":
                self._send_json(200, self.server.service.start_grower())
                return

            if path == "/grower/stop":
                self._send_json(200, self.server.service.stop_grower())
                return

            self._send_json(404, {"error": f"unknown route: {path}"})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_internal_error(exc)

    # ------------------------------------------------------------ 工具

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b"{}"
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid json: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body 必须是对象")
        return data

    def _require_auth(self, path: str) -> bool:
        expected = self.server.service.api_key
        if not expected:
            return True

        # 健康探针默认放行，避免部署平台被鉴权卡死。
        if path in ("/health", "/healthz"):
            return True

        presented = (self.headers.get("X-API-Key") or "").strip()
        if not presented:
            auth = (self.headers.get("Authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                presented = auth[7:].strip()

        if presented == expected:
            return True

        self._send_json(401, {"error": "unauthorized", "message": "missing or invalid api key"})
        return False

    def _send_internal_error(self, exc: Exception) -> None:
        rid = uuid.uuid4().hex[:12]
        trace = traceback.format_exc()
        print(
            f"[loam][error][{rid}] {type(exc).__name__}: {exc}\n{trace}",
            file=sys.stderr,
            flush=True,
        )
        self._send_json(500, {"error": "internal_error", "request_id": rid})

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # 测试里尽量安静。需要时可改成 print。
        return


def build_server(service: LoamService, host: str = "127.0.0.1", port: int = 8765) -> LoamHTTPServer:
    return LoamHTTPServer((host, port), service)


def run_server(service: LoamService, host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = build_server(service, host=host, port=port)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        service.close()


def _normalise_turns(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把输入统一成 Journal.append_batch 需要的结构。"""
    if isinstance(payload.get("turns"), list):
        turns = payload["turns"]
        return [_one_turn(x) for x in turns if isinstance(x, dict)]

    if isinstance(payload.get("messages"), list):
        base_turn = int(payload.get("turn") or 1)
        turns: List[Dict[str, Any]] = []
        for i, msg in enumerate(payload["messages"]):
            if not isinstance(msg, dict):
                continue
            t = dict(msg)
            t.setdefault("turn", base_turn + i)
            turns.append(_one_turn(t))
        return turns

    if all(k in payload for k in ("turn", "role", "content")):
        return [_one_turn(payload)]

    return []


def _one_turn(raw: Dict[str, Any]) -> Dict[str, Any]:
    turn = int(raw.get("turn"))
    role = str(raw.get("role") or "").strip()
    content = str(raw.get("content") or "").strip()
    if not role or not content:
        raise ValueError("每条 turn 都需要 role 和 content")

    out: Dict[str, Any] = {
        "turn": turn,
        "role": role,
        "content": content,
    }

    if "wrote_at" in raw:
        out["wrote_at"] = float(raw["wrote_at"])
    if "meta" in raw and isinstance(raw["meta"], dict):
        out["meta"] = raw["meta"]
    return out


_LIGHTWEIGHT_REPLIES = {
    "嗯",
    "好的",
    "好",
    "收到",
    "知道了",
    "明白",
    "明白了",
    "ok",
    "okay",
    "got it",
    "roger",
}


def _prefilter_evidence(turns: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    """轻量预过滤：优先保留用户输入，尽量剔除纯 ACK 噪声。"""
    kept: List[Dict[str, Any]] = []
    dropped = 0

    for t in turns:
        role = str(t.get("role") or "").strip().lower()
        content = str(t.get("content") or "")
        normalized = " ".join(content.strip().split())

        # 只过滤 assistant 的纯确认短句，避免稀释后续提炼质量。
        if role == "assistant" and normalized:
            low = normalized.lower()
            if low in _LIGHTWEIGHT_REPLIES or (len(normalized) <= 2 and low not in {"不", "行"}):
                dropped += 1
                continue

        kept.append(t)

    return kept, dropped


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    return default
