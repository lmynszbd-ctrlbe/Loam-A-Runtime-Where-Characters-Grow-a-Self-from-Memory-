#!/usr/bin/env python3
"""强制流程代理（OpenAI 兼容入口，支持多上游）。

固定流程（不依赖模型工具调用）：
  1) 取 loam context
  2) 调上游模型
  3) 把本轮 user+assistant 原文落 loam ingest

多上游能力：
- /v1/models 会聚合所有上游，并把模型 id 前缀成 provider/model
- /v1/chat/completions 可按以下方式选上游：
  a) model="provider/model"
  b) model="provider:model"
  c) Header: X-Upstream: provider
  d) 都不传则走默认上游
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROXY_HOST = os.environ.get("PROXY_HOST", "0.0.0.0")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8781"))

# Security: proxy requires a local token to prevent unauthorized access
# from other processes or browser extensions on the same machine.
def _loam_path(sub_path: str) -> Path:
    """Return a path inside LOAM_HOME (or ~/.loam / Termux fallback)."""
    if "LOAM_HOME" in os.environ:
        return Path(os.environ["LOAM_HOME"]) / sub_path
    p = Path(f"~/.loam/{sub_path}").expanduser()
    if not p.parent.exists() and os.name != "nt":
        termux_p = Path(f"/data/data/com.termux/files/home/.loam/{sub_path}")
        if termux_p.parent.exists():
            return termux_p
    return p


PROXY_TOKEN_FILE = Path(os.environ.get("PROXY_TOKEN_FILE", _loam_path("proxy_token")))
PROXY_TOKEN = os.environ.get("PROXY_TOKEN", "").strip()
if not PROXY_TOKEN:
    if PROXY_TOKEN_FILE.exists():
        PROXY_TOKEN = PROXY_TOKEN_FILE.read_text(encoding="utf-8").strip()
    else:
        PROXY_TOKEN = "loam-" + secrets.token_hex(16)
        PROXY_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROXY_TOKEN_FILE.write_text(PROXY_TOKEN, encoding="utf-8")
        os.chmod(PROXY_TOKEN_FILE, 0o600)
TOKEN_AUTH_REQUIRED = os.environ.get("PROXY_NO_AUTH", "0") not in ("1", "true", "True")


LOAM_URL = os.environ.get("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")

DEFAULT_SESSION = os.environ.get("LOAM_SESSION", "proxy-default")
LEARN_ON_CONTEXT = os.environ.get("LOAM_CONTEXT_LEARN", "0") not in ("0", "false", "False")
FORCE_DIGEST = os.environ.get("LOAM_FORCE_DIGEST", "0") in ("1", "true", "True")

STORE = _loam_path("proxy_state.json")
UPSTREAMS_CONFIG = _loam_path("upstreams.json")
UPSTREAM_DEFAULT = os.environ.get("UPSTREAM_DEFAULT", "").strip()

# 兼容单上游老参数
LEGACY_BASE_URL = os.environ.get("UPSTREAM_BASE_URL", "https://api.deepseek.com").rstrip("/")
LEGACY_API_KEY = os.environ.get("UPSTREAM_API_KEY", "").strip()
LEGACY_MODEL = os.environ.get("UPSTREAM_MODEL", "deepseek-chat").strip()

_LOCK = threading.Lock()


def _load_state() -> Dict[str, int]:
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, int]) -> None:
    STORE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_turn(session: str) -> int:
    with _LOCK:
        state = _load_state()
        n = int(state.get(session, 0)) + 1
        state[session] = n
        _save_state(state)
        return n


def _json_post(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 120.0,
    retries: int = 2,
) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hs = {"Content-Type": "application/json"}
    if headers:
        hs.update(headers)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=hs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError:
            # HTTP errors (4xx/5xx) are meaningful — don't retry, bubble up.
            raise
        except Exception as exc:  # noqa: BLE001
            # Transient transport errors (RemoteDisconnected, reset, timeout).
            last_exc = exc
            if attempt < retries:
                print(f"[proxy] upstream POST retry {attempt + 1}/{retries} after {type(exc).__name__}", flush=True)
                time.sleep(0.8 * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc
    return {}


# Fields we forward to the upstream OpenAI-compatible API. Anything else the
# client sends (e.g. Operit-specific extras) is dropped so it can't make the
# upstream reject the request or close the connection unexpectedly.
_UPSTREAM_ALLOWED_FIELDS = {
    "model", "messages", "temperature", "top_p", "max_tokens",
    "max_completion_tokens", "frequency_penalty", "presence_penalty",
    "stop", "n", "seed", "response_format", "logit_bias", "user",
    "tools", "tool_choice",
}


def _clean_upstream_payload(req: Dict[str, Any], stream: Optional[bool] = None) -> Dict[str, Any]:
    """Keep only standard fields the upstream understands."""
    out: Dict[str, Any] = {}
    for k, v in req.items():
        if k in _UPSTREAM_ALLOWED_FIELDS and v is not None:
            out[k] = v
    if stream is not None:
        out["stream"] = stream
    return out


def _json_post_stream(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Call upstream with stream=True, parse SSE chunks into a non-stream JSON.

    Some models only support streaming. We collect all SSE deltas and assemble
    a complete OpenAI chat.completion response for loam ingest.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hs = {"Content-Type": "application/json"}
    if headers:
        hs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    # Parse SSE: each line that starts with "data: " followed by JSON
    cid = ""
    model = ""
    created = 0
    role = "assistant"
    content_parts: List[str] = []
    reasoning_parts: List[str] = []
    finish = "stop"
    for line in raw.split("\n"):
        line = line.strip()
        if not line or line == "data: [DONE]":
            continue
        if line.startswith("data: "):
            try:
                obj = json.loads(line[6:])
                cid = str(obj.get("id") or cid)
                model = str(obj.get("model") or model)
                created = int(obj.get("created") or created)
                for choice in obj.get("choices", []):
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta", {}) or {}
                    role = str(delta.get("role") or role)
                    r = delta.get("reasoning_content")
                    if r:
                        reasoning_parts.append(str(r))
                    c = delta.get("content")
                    if c:
                        content_parts.append(str(c))
                    if choice.get("finish_reason"):
                        finish = str(choice.get("finish_reason"))
            except json.JSONDecodeError:
                continue
    msg: Dict[str, Any] = {"role": role, "content": "".join(content_parts)}
    if reasoning_parts:
        msg["reasoning_content"] = "".join(reasoning_parts)
    return {
        "id": cid or f"chatcmpl-{secrets.token_hex(8)}",
        "object": "chat.completion",
        "created": created or int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": msg,
            "finish_reason": finish,
        }],
    }


def _json_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    hs = {"Accept": "application/json"}
    if headers:
        hs.update(headers)
    req = urllib.request.Request(url, headers=hs, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: List[str] = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                out.append(str(p.get("text", "")))
        return "\n".join([x for x in out if x.strip()])
    return str(content or "")


def _last_user(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            text = _extract_text(m.get("content"))
            if text.strip():
                return text.strip()
    return ""


def _assistant_text(resp: Dict[str, Any]) -> str:
    try:
        msg = resp["choices"][0]["message"]
        parts: List[str] = []
        reasoning = (msg.get("reasoning_content") or "").strip()
        if reasoning:
            parts.append(f"【思考过程】\n{reasoning}")
        content = _extract_text(msg.get("content", "")).strip()
        if content:
            parts.append(content)
        return "\n\n".join(parts)
    except Exception:
        return ""


def _session_from(req_body: Dict[str, Any], headers: Dict[str, str]) -> str:
    s = headers.get("x-loam-session", "").strip()
    if s:
        return s
    user = str(req_body.get("user") or "").strip()
    if user:
        return user
    return DEFAULT_SESSION


def _build_messages_with_context(orig: List[Dict[str, Any]], ctx_text: str) -> List[Dict[str, Any]]:
    # Token 预算: 上下文最多占 2000 字符，优先保留高能量部分
    ctx_budget = 2000
    if len(ctx_text) > ctx_budget:
        # 按段落分割，优先保留前面的（高能量段落在前）
        paras = ctx_text.split("\n\n")
        kept = []
        total = 0
        for p in paras:
            if total + len(p) <= ctx_budget:
                kept.append(p)
                total += len(p) + 2
            else:
                break
        ctx_text = "\n\n".join(kept)
    mem = {
        "role": "system",
        "content": (
            "以下是角色的长期记忆上下文（由 loam 提供）。"
            "请作为隐式背景使用，不要逐条复述。\n\n" + ctx_text
        ),
    }
    return [mem] + orig


def _trim_messages(messages: List[Dict[str, Any]], max_messages: int = 50) -> List[Dict[str, Any]]:
    """Truncate message history to avoid overwhelming upstream APIs.

    Keeps the first system message (if any) and the most recent messages.
    Many clients send hundreds of messages; most upstreams can't handle that.
    """
    if len(messages) <= max_messages:
        return messages
    first = messages[0] if messages and messages[0].get("role") == "system" else None
    rest = messages[1:] if first else messages
    trimmed = rest[-(max_messages - (1 if first else 0)):]
    if first:
        return [first] + trimmed
    return trimmed


def _load_upstreams() -> Tuple[Dict[str, Dict[str, str]], str]:
    providers: Dict[str, Dict[str, str]] = {}
    cfg_default = ""

    if UPSTREAMS_CONFIG.exists():
        try:
            cfg = json.loads(UPSTREAMS_CONFIG.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                cfg_default = str(cfg.get("default") or "").strip()
                raw_providers = cfg.get("providers") or {}
                if isinstance(raw_providers, dict):
                    for name, item in raw_providers.items():
                        if not isinstance(item, dict):
                            continue
                        base = str(item.get("base_url") or "").strip().rstrip("/")
                        key = str(item.get("api_key") or "").strip()
                        dmodel = str(item.get("default_model") or item.get("model") or "").strip()
                        if not base:
                            continue
                        providers[str(name)] = {
                            "base_url": base,
                            "api_key": key,
                            "default_model": dmodel,
                        }
        except Exception:
            providers = {}
            cfg_default = ""

    if not providers:
        providers["default"] = {
            "base_url": LEGACY_BASE_URL,
            "api_key": LEGACY_API_KEY,
            "default_model": LEGACY_MODEL,
        }

    default_name = UPSTREAM_DEFAULT or cfg_default
    if not default_name or default_name not in providers:
        default_name = next(iter(providers.keys()))

    return providers, default_name


UPSTREAMS: Dict[str, Dict[str, str]] = {}
DEFAULT_UPSTREAM: str = ""

# 初始化加载
UPSTREAMS, DEFAULT_UPSTREAM = _load_upstreams()
# 记录配置文件的最后修改时间，用于热加载
_upstreams_mtime: float = UPSTREAMS_CONFIG.stat().st_mtime if UPSTREAMS_CONFIG.exists() else 0


def _maybe_reload_upstreams() -> None:
    """如果 upstreams.json 被修改过，重新加载。"""
    global UPSTREAMS, DEFAULT_UPSTREAM, _upstreams_mtime
    try:
        if UPSTREAMS_CONFIG.exists():
            mtime = UPSTREAMS_CONFIG.stat().st_mtime
            if mtime != _upstreams_mtime:
                UPSTREAMS, DEFAULT_UPSTREAM = _load_upstreams()
                _upstreams_mtime = mtime
    except Exception:
        pass  # 保持当前配置，不中断请求


def _pick_upstream(req_model: str, header_upstream: str = "") -> Tuple[str, str, str]:
    """返回 (provider, upstream_model, exposed_model)。"""
    provider = ""
    model = req_model.strip()

    if header_upstream and header_upstream in UPSTREAMS:
        provider = header_upstream

    if not provider and model:
        if "/" in model:
            p, m = model.split("/", 1)
            if p in UPSTREAMS and m.strip():
                provider, model = p, m.strip()
        elif ":" in model:
            p, m = model.split(":", 1)
            if p in UPSTREAMS and m.strip():
                provider, model = p, m.strip()

    if not provider:
        provider = DEFAULT_UPSTREAM

    cfg = UPSTREAMS.get(provider)
    if not cfg:
        raise ValueError(f"未知上游 provider: {provider}")

    if not model:
        model = cfg.get("default_model", "").strip()
    if not model:
        raise ValueError(f"provider={provider} 未指定模型，且无 default_model")

    exposed = f"{provider}/{model}"
    return provider, model, exposed


def _provider_headers(provider: str) -> Dict[str, str]:
    key = (UPSTREAMS.get(provider) or {}).get("api_key", "").strip()
    if not key:
        raise ValueError(f"provider={provider} 缺少 api_key")
    return {"Authorization": f"Bearer {key}"}


def _provider_base(provider: str) -> str:
    base = (UPSTREAMS.get(provider) or {}).get("base_url", "").strip().rstrip("/")
    if not base:
        raise ValueError(f"provider={provider} 缺少 base_url")
    return base


def _provider_api_base(provider: str) -> str:
    """Return base URL for /v1/... endpoints, tolerating trailing /v1 in config."""
    base = _provider_base(provider)
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _models_merged() -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for name in UPSTREAMS.keys():
        try:
            data = _json_get(
                f"{_provider_api_base(name)}/v1/models",
                headers=_provider_headers(name),
                timeout=30,
            )
            items = data.get("data") if isinstance(data, dict) else None
            if isinstance(items, list) and items:
                for m in items:
                    if not isinstance(m, dict):
                        continue
                    mid = str(m.get("id") or "").strip()
                    if not mid:
                        continue
                    c = dict(m)
                    c["id"] = f"{name}/{mid}"
                    c["owned_by"] = f"{name}:{m.get('owned_by', '')}".strip(":")
                    out.append(c)
                continue
        except Exception as exc:
            return {"object": "list", "data": [], "_error": f"{name}: {type(exc).__name__}: {exc}"}

        # fallback: 至少用 default_model 生成一个条目，让用户能下拉选择
        dmodel = (UPSTREAMS.get(name) or {}).get("default_model", "").strip()
        if dmodel:
            out.append({
                "id": f"{name}/{dmodel}",
                "object": "model",
                "owned_by": name,
            })
    return {"object": "list", "data": out}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        _maybe_reload_upstreams()
        if TOKEN_AUTH_REQUIRED and not self._check_token():
            self._send(401, {"error": {"message": "unauthorized: missing or invalid proxy token. Set PROXY_TOKEN env or check ~/.loam/proxy_token"}})
            return
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "not found"}})
            return

        try:
            req = self._read_json()
            req_model = str(req.get("model") or "")
            wants_stream = bool(req.get("stream"))
            print(f"[proxy] POST /v1/chat/completions model={req_model} stream={wants_stream} messages={len(req.get('messages', []))}", flush=True)
            # loam needs the full assistant text to ingest, so we always call the
            # upstream in non-streaming mode. If the client asked for stream=true,
            # we re-emit the final answer as SSE chunks below so streaming clients
            # (e.g. Operit) don't time out waiting for the first byte.
            if wants_stream:
                req["stream"] = False

            messages = req.get("messages")
            if not isinstance(messages, list) or not messages:
                self._send(400, {"error": {"message": "messages 不能为空"}})
                return

            headers_low = {k.lower(): v for k, v in self.headers.items()}
            session = _session_from(req, headers_low)
            user_text = _last_user(messages)

            # 1) 强制取 context（失败不中断主链路）
            ctx_text = ""
            if user_text:
                try:
                    c = _json_post(
                        f"{LOAM_URL}/context",
                        {"query": user_text, "learn": LEARN_ON_CONTEXT},
                        timeout=30,
                    )
                    ctx_text = str(c.get("text") or "")
                except Exception as exc:
                    print(f"[proxy] context fetch failed: {type(exc).__name__}: {exc}")
                    ctx_text = ""

            merged = _build_messages_with_context(messages, ctx_text) if ctx_text else messages

            # 2) 选上游并转发
            req_model = str(req.get("model") or "")
            hdr_up = str(headers_low.get("x-upstream") or "").strip()
            provider, upstream_model, exposed_model = _pick_upstream(req_model, hdr_up)

            up_payload = _clean_upstream_payload(req, stream=False)
            up_payload["model"] = upstream_model
            up_payload["messages"] = _trim_messages(merged)

            up_url = f"{_provider_api_base(provider)}/v1/chat/completions"
            up_headers = _provider_headers(provider)

            # Try non-streaming first (loam needs full text for ingest).
            # If the upstream rejects it (400) with a hint about streaming,
            # automatically fall back to streaming and reassemble the SSE.
            up_resp: Dict[str, Any]
            used_stream = False
            try:
                up_resp = _json_post(up_url, up_payload, headers=up_headers)
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace")
                if e.code == 400 and ("stream" in raw.lower() or "streaming" in raw.lower()):
                    print(f"[proxy] upstream rejected non-stream, falling back to stream=true", flush=True)
                    up_payload["stream"] = True
                    up_resp = _json_post_stream(up_url, up_payload, headers=up_headers)
                    used_stream = True
                else:
                    raise
            print(f"[proxy] POST {up_url} → model={upstream_model} → OK{' (stream)' if used_stream else ''}", flush=True)

            # 3) 强制落本轮原文到 loam
            assistant = _assistant_text(up_resp)
            if user_text and assistant:
                try:
                    turn = _next_turn(session)
                    _json_post(
                        f"{LOAM_URL}/ingest",
                        {
                            "session": session,
                            "turns": [
                                {"turn": turn, "role": "user", "content": user_text},
                                {"turn": turn, "role": "assistant", "content": assistant},
                            ],
                            "client": "forced-flow-proxy",
                            "model": exposed_model,
                            "meta": {"provider": provider, "upstream_model": upstream_model},
                        },
                        timeout=30,
                    )
                    if FORCE_DIGEST:
                        _json_post(f"{LOAM_URL}/digest", {}, timeout=60)
                except Exception as exc:
                    print(f"[proxy] ingest failed: {type(exc).__name__}: {exc}")

            if wants_stream:
                self._send_stream(up_resp, exposed_model)
            else:
                self._send(200, up_resp)
        except ValueError as e:
            self._send(400, {"error": {"message": str(e)}})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            print(f"[proxy] HTTP {e.code} from upstream: {raw[:300]}", flush=True)
            try:
                data = json.loads(raw)
            except Exception:
                data = {"error": {"message": raw or str(e)}}
            self._send(e.code, data)
        except Exception as e:  # noqa: BLE001
            print(f"[proxy] {type(e).__name__}: {e}", flush=True)
            name = type(e).__name__
            if name in ("RemoteDisconnected", "IncompleteRead", "ConnectionResetError") or "RemoteDisconnected" in str(e):
                msg = ("上游 API 中断了连接（可能是该模型不可用/超载，或历史消息过多）。"
                       "请换一个模型，或减少对话历史后重试。")
            else:
                msg = f"{name}: {e}"
            self._send(502, {"error": {"message": msg, "type": name}})

    def do_GET(self) -> None:  # noqa: N802
        _maybe_reload_upstreams()
        if self.path == "/health":
            self._send(
                200,
                {
                    "ok": True,
                    "name": "forced-flow-proxy",
                    "time": time.time(),
                    "default_upstream": DEFAULT_UPSTREAM,
                    "upstreams": list(UPSTREAMS.keys()),
                },
            )
            return

        if self.path == "/v1/models":
            self._send(200, _models_merged())
            return

        self._send(404, {"error": {"message": "not found"}})


    def _check_token(self) -> bool:
        """Verify the request carries the correct proxy token."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:] == PROXY_TOKEN
        # Also accept X-Proxy-Token header for clients that can't set Authorization
        xt = self.headers.get("X-Proxy-Token", "")
        if xt:
            return xt == PROXY_TOKEN
        return False

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b"{}"
        if not raw.strip():
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body 必须是对象")
        return data

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError):
            # Client (e.g. Operit) gave up / closed the socket before we replied.
            print("[proxy] client disconnected before response was sent", flush=True)

    def _send_stream(self, up_resp: Dict[str, Any], model: str) -> None:
        """Re-emit a non-streamed upstream answer as OpenAI SSE chunks.

        Streaming clients (Operit) expect text/event-stream. We already have the
        full answer, so we send it as one content delta followed by [DONE].
        """
        text = _assistant_text(up_resp)
        created = int(time.time())
        cid = str(up_resp.get("id") or f"chatcmpl-{secrets.token_hex(8)}")
        try:
            msg = up_resp["choices"][0]["message"]
        except Exception:
            msg = {}
        reasoning = (msg.get("reasoning_content") or "").strip()
        content = _extract_text(msg.get("content", "")).strip()
        tool_calls = msg.get("tool_calls")

        def chunk(delta: Dict[str, Any], finish: Optional[str] = None) -> bytes:
            payload = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(chunk({"role": "assistant"}))
            if reasoning:
                self.wfile.write(chunk({"reasoning_content": reasoning}))
            if content:
                self.wfile.write(chunk({"content": content}))
            if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                self.wfile.write(chunk({"tool_calls": tool_calls}))
            self.wfile.write(chunk({}, finish="stop"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print("[proxy] client disconnected during stream", flush=True)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> int:
    import socket
    srv = ThreadingHTTPServer((PROXY_HOST, PROXY_PORT), Handler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f"forced-flow-proxy listening on http://{PROXY_HOST}:{PROXY_PORT}")
    if TOKEN_AUTH_REQUIRED:
        print(f"proxy token: {PROXY_TOKEN} (saved to {PROXY_TOKEN_FILE})")
        print(f"Add header: Authorization: Bearer {PROXY_TOKEN}")
        print(f"Or set env: PROXY_NO_AUTH=1 to disable (not recommended)")
    print(f"loam={LOAM_URL} default_upstream={DEFAULT_UPSTREAM} upstreams={list(UPSTREAMS.keys())}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())