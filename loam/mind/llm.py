"""向内思考用的那个脑子。

对外说话用的是客户端自己配的模型（你在 Operit 里填什么就是什么）。
这里是另一回事 —— 它只在后台用，只做一件事：把生料煮成熟料。

为什么要固定成同一个模型：自我审阅的标准必须稳定。今天用 A 判断
"这件事算不算印证了它谨慎"，明天换 B，尺子就变了，长出来的东西
会带上换模型的痕迹而不是经历的痕迹。

只用标准库。transport 可以替换，所以离线也能完整测试。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


class BrainError(RuntimeError):
    """脑子没能给出可用的回答。"""


class BrainUnavailable(BrainError):
    """压根没配脑子 —— 没有 key，或者接口连不上。"""


#: 一次请求最多重试几次。后台任务不着急，宁可慢也别丢料。
RETRIES = 3
#: 重试的基础间隔（秒），每次翻倍。
BACKOFF = 2.0
#: ask_json 遇到截断时，token 预算翻倍的上限。推理模型思考可能很长，
#: 给足空间让它写完思考再吐 JSON；触顶还截断就只能靠重问兜底。
_MAX_JSON_BUDGET = 16384

@dataclass
class Usage:
    """花了多少 token。后台会跑很多次，这个得记着。"""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    route_calls: Dict[str, int] = field(default_factory=dict)

    def add(self, prompt: int, completion: int, route: str = "primary") -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        key = route.strip() or "primary"
        self.route_calls[key] = int(self.route_calls.get(key, 0)) + 1

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> Dict[str, object]:
        return {
            "调用次数": self.calls,
            "输入token": self.prompt_tokens,
            "输出token": self.completion_tokens,
            "合计": self.total,
            "路由调用": dict(sorted(self.route_calls.items())),
        }



Transport = Callable[[str, Dict[str, Any], float], Dict[str, Any]]
"""(url, payload, timeout) -> 解析好的响应字典。替换它就能离线测试。"""


def http_transport(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    """真的发出去。纯 urllib，不引第三方。"""
    api_key = payload.pop("_api_key")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class Brain:
    """后台反思用的模型。

    Attributes:
        api_key: 放在不上传仓库的文件里，或者环境变量。
        base_url: 兼容 OpenAI 格式的地址。DeepSeek 默认即可。
        model: 固定不动。换模型等于换尺子。
    """

    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"

    # 低成本路由：用于把抽取/核对等子任务切到更便宜模型。
    low_cost_api_key: str = ""
    low_cost_base_url: str = ""
    low_cost_model: str = ""
    low_cost_enabled: bool = False
    low_cost_phases: Sequence[str] = field(
        default_factory=lambda: ("extract", "observe", "dossier", "drift")
    )

    timeout: float = 120.0
    retries: int = RETRIES
    transport: Transport = http_transport
    usage: Usage = field(default_factory=Usage)

    #: 每次调用之后的回调，用于外部记账/打日志。
    on_call: Optional[Callable[[str, str], None]] = None

    @property
    def available(self) -> bool:
        if self.transport is not http_transport:
            return True
        if bool((self.api_key or "").strip()):
            return True
        if (
            self.low_cost_enabled
            and bool((self.low_cost_api_key or "").strip())
            and bool((self.low_cost_model or "").strip())
        ):
            return True
        return False

    def set_low_cost_enabled(self, enabled: bool) -> None:
        self.low_cost_enabled = bool(enabled)

    def _pick_route(self, phase: str = "") -> Dict[str, str]:
        phase_key = str(phase or "").strip().lower()
        low_phases = {
            str(p).strip().lower()
            for p in (self.low_cost_phases or [])
            if str(p).strip()
        }
        use_low = (
            self.low_cost_enabled
            and bool((self.low_cost_model or "").strip())
            and phase_key in low_phases
        )

        if use_low:
            return {
                "route": f"low_cost:{phase_key}",
                "api_key": (self.low_cost_api_key or self.api_key).strip(),
                "base_url": (self.low_cost_base_url or self.base_url).strip(),
                "model": (self.low_cost_model or self.model).strip(),
            }

        return {
            "route": "primary",
            "api_key": (self.api_key or "").strip(),
            "base_url": (self.base_url or "").strip(),
            "model": (self.model or "").strip(),
        }

    # ------------------------------------------------------------ 基本问答

    def ask(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        phase: str = "",
    ) -> str:
        """问一句，拿回文本。

        温度默认压得很低 —— 这不是创作，是审阅。同一批经历应该
        得出大致相同的结论，随机性在这里只会变成漂移。
        """
        text, _ = self._ask_raw(
            system, user, temperature=temperature, max_tokens=max_tokens, phase=phase
        )
        return text

    def _ask_raw(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        phase: str = "",
    ) -> tuple[str, str]:
        """底层问答，除了文本还回传 finish_reason，供 ask_json 判断截断。"""
        route = self._pick_route(phase=phase)
        if self.transport is http_transport and not route["api_key"]:
            raise BrainUnavailable(
                "还没配后台反思用的模型。把 key 写进 ~/.loam/secrets.json 的 api_key。"
            )
        url = route["base_url"].rstrip("/").rstrip("/v1") + "/v1/chat/completions"
        payload: Dict[str, Any] = {
            "_api_key": route["api_key"],
            "model": route["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                data = self.transport(url, dict(payload), self.timeout)
                text = _extract_text(data)
                finish = _finish_reason(data)
                u = data.get("usage") or {}
                self.usage.add(
                    int(u.get("prompt_tokens", 0)),
                    int(u.get("completion_tokens", 0)),
                    route=route["route"],
                )
                if self.on_call:
                    self.on_call(f"[{route['route']}] {user[:200]}", text[:200])
                return text, finish
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(BACKOFF * (2 ** attempt))
            except BrainError as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(BACKOFF)
        raise BrainUnavailable(f"连了 {self.retries} 次都没成：{last}") from last

    # ------------------------------------------------------------ 结构化

    def ask_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
        phase: str = "",
    ) -> Any:
        """问一句，要一段 JSON 回来。
        模型很爱在 JSON 外面裹 ```json 或者写几句解释，全都容忍掉。
        推理模型还会先写一大段思考，把 token 预算吃光、JSON 被截断 —— 遇到
        finish_reason=='length' 就自动把预算翻倍再问，直到写得下或触顶。
        实在解析不出来，就重问一次并把错误告诉它。
        """
        prompt = user
        budget = max(256, int(max_tokens))
        last: Optional[Exception] = None
        for _ in range(max(1, retries)):
            raw, finish = self._ask_raw(
                system,
                prompt,
                temperature=temperature,
                max_tokens=budget,
                phase=phase,
            )
            # 被截断：思考写太长，JSON 没吐完。加预算重来，别急着解析残料。
            while finish == "length" and budget < _MAX_JSON_BUDGET:
                budget = min(_MAX_JSON_BUDGET, budget * 2)
                raw, finish = self._ask_raw(
                    system,
                    prompt,
                    temperature=temperature,
                    max_tokens=budget,
                    phase=phase,
                )
            try:
                return parse_json(raw)
            except ValueError as exc:
                last = exc
                # 解析失败若仍疑似截断，下一轮直接给足预算。
                if finish == "length":
                    budget = _MAX_JSON_BUDGET
                prompt = (
                    f"{user}\n\n上一次你的回答无法被解析：{exc}\n"
                    "只输出 JSON 本身，不要任何解释、不要思考过程、不要代码块标记。"
                )
        raise BrainError(f"要不到能解析的 JSON：{last}")


# ---------------------------------------------------------------- 解析


def _extract_text(data: Dict[str, Any]) -> str:
    try:
        choices = data["choices"]
        msg = choices[0]["message"]
        text = msg.get("content") or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise BrainError(f"响应结构看不懂：{str(data)[:300]}") from exc
    if not text.strip():
        raise BrainError("响应是空的")
    return text


def _finish_reason(data: Dict[str, Any]) -> str:
    """拿到本次生成为什么停下来。推理模型常见 'length' —— 思考写太长把
    token 预算吃光，JSON 还没吐就被截断。ask_json 靠它决定是否加预算重试。"""
    try:
        return str(data["choices"][0].get("finish_reason") or "").strip().lower()
    except (KeyError, IndexError, TypeError):
        return ""


_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def parse_json(raw: str) -> Any:
    """从一段可能很脏的文本里把 JSON 抠出来。"""
    text = raw.strip()

    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 退一步：找最外层的一对括号
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            chunk = text[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue

    # 最后手段：推理模型可能把思考过程写在 JSON 前面。
    # 找第一个出现在行首的 { 或 [，从那里开始解析。
    for m2 in re.finditer(r'(?:^|\n)\s*([\[{])', text):
        idx = m2.start(1)
        chunk = text[idx:]
        for opener, closer in (("[", "]"), ("{", "}")):
            if chunk[0] == opener:
                end = chunk.rfind(closer)
                if end > 0:
                    try:
                        return json.loads(chunk[:end + 1])
                    except json.JSONDecodeError:
                        continue

    raise ValueError(f"不是 JSON：{text[:200]}")


# ---------------------------------------------------------------- 配置


SECRETS_NAME = "secrets.json"
#: 后台面板保存 provider 配置的文件（base_url / api_key / default_model）。
UPSTREAMS_NAME = "upstreams.json"
#: 常见占位文本，命中就当没填，避免把模板值当成真 key 发出去。
_PLACEHOLDER_HINTS = ("请替换", "替换为", "your_", "your-", "yourkey", "sk-xxx", "xxxxxx")


def _looks_placeholder(value: str) -> bool:
    v = str(value or "").strip()
    if not v:
        return True
    low = v.lower()
    return any(h in v or h in low for h in _PLACEHOLDER_HINTS)


def _load_upstream_default(home_path: Path) -> Dict[str, str]:
    """从面板写的 upstreams.json 里取默认 provider，作为 secrets.json 的兜底。

    结构：{"default": "<name>", "providers": {"<name>": {base_url, api_key, default_model}}}
    只在 secrets.json 没配好时用，占位模板值会被忽略。
    """
    path = home_path / UPSTREAMS_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    providers = data.get("providers")
    if not isinstance(providers, dict) or not providers:
        return {}
    name = data.get("default")
    prov = providers.get(name) if isinstance(name, str) else None
    if not isinstance(prov, dict):
        prov = next((p for p in providers.values() if isinstance(p, dict)), None)
    if not isinstance(prov, dict):
        return {}
    out: Dict[str, str] = {}
    base_url = str(prov.get("base_url", "")).strip()
    api_key = str(prov.get("api_key", "")).strip()
    model = str(prov.get("default_model", "")).strip()
    if base_url and not _looks_placeholder(base_url):
        out["base_url"] = base_url
    if api_key and not _looks_placeholder(api_key):
        out["api_key"] = api_key
    if model and not _looks_placeholder(model):
        out["model"] = model
    return out


def load_brain(home: str | Path = "~/.loam", **overrides: Any) -> Brain:
    """按 环境变量 > secrets.json > upstreams.json(面板) > 默认值 的顺序装配脑子。

    secrets.json 永远不进仓库（.gitignore 里已经排掉）。
    没配 key 也不报错 —— 返回一个 available=False 的脑子，
    这样存储和内生机制依然能跑，只是不能煮料。

    兜底读 upstreams.json：用户在后台面板填的 provider 会写进那里，
    以前 digest/grower 看不到它，导致"面板配好了但消化还是超时"。
    """
    cfg: Dict[str, Any] = {}
    home_path = Path(home).expanduser()
    path = home_path / SECRETS_NAME
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    upstream = _load_upstream_default(home_path)
    key = os.environ.get("LOAM_API_KEY") or cfg.get("api_key") or upstream.get("api_key", "")
    base = (
        os.environ.get("LOAM_BASE_URL")
        or cfg.get("base_url")
        or upstream.get("base_url")
        or "https://api.deepseek.com"
    )
    model = (
        os.environ.get("LOAM_MODEL")
        or cfg.get("model")
        or upstream.get("model")
        or "deepseek-chat"
    )

    low_key = os.environ.get("LOAM_LOW_COST_API_KEY") or cfg.get("low_cost_api_key", "")
    low_base = os.environ.get("LOAM_LOW_COST_BASE_URL") or cfg.get("low_cost_base_url", "")
    low_model = os.environ.get("LOAM_LOW_COST_MODEL") or cfg.get("low_cost_model", "")
    low_enabled = _coerce_bool_env(
        os.environ.get("LOAM_LOW_COST_ENABLED"),
        default=bool(cfg.get("low_cost_enabled", False)),
    )
    low_phases = _coerce_phase_list(
        os.environ.get("LOAM_LOW_COST_PHASES"),
        cfg.get("low_cost_phases"),
    )

    seed_narrative = os.environ.get('LOAM_SEED_NARRATIVE') or cfg.get('seed_narrative', '').strip()

    
    brain = Brain(
        api_key=key,
        base_url=base,
        model=model,
        low_cost_api_key=low_key,
        low_cost_base_url=low_base,
        low_cost_model=low_model,
        low_cost_enabled=low_enabled,
        low_cost_phases=low_phases,
    )
    for k, v in overrides.items():
        setattr(brain, k, v)
    brain.seed_narrative = seed_narrative
    return brain


def _coerce_bool_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return bool(default)


def _coerce_phase_list(env_value: Optional[str], cfg_value: Any) -> Sequence[str]:
    if env_value and str(env_value).strip():
        return tuple(
            x.strip().lower()
            for x in str(env_value).split(",")
            if x.strip()
        )
    if isinstance(cfg_value, list):
        out = [str(x).strip().lower() for x in cfg_value if str(x).strip()]
        if out:
            return tuple(out)
    return ("extract", "observe", "dossier", "drift")


def write_secrets_template(home: str | Path = "~/.loam") -> Path:

    """生成一份填 key 的模板，已存在则不覆盖。"""
    d = Path(home).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    path = d / SECRETS_NAME
    if not path.exists():
        path.write_text(
            json.dumps(
                {
                    "api_key": "",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "low_cost_enabled": False,
                    "low_cost_api_key": "",
                    "low_cost_base_url": "",
                    "low_cost_model": "",
                    "low_cost_phases": ["extract", "observe", "dossier", "drift"],
                "seed_narrative": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path


# ---------------------------------------------------------------- 测试替身


class ScriptedBrain(Brain):
    """按剧本回答的假脑子。用于离线跑通整条消化链路。

    剧本里的每一项可以是：
      * 字符串 —— 原样返回
      * 可 JSON 序列化的对象 —— 序列化后返回
      * 可调用对象 —— 调用它并把 user 提示词传进去，用返回值当回答。
        这一档是为了让测试能引用"这一批刚刚被抽出来的事件 id"，
        那些 id 在写剧本的时候还不存在。
    """

    def __init__(self, replies: List[Any], model: str = "scripted") -> None:
        super().__init__(api_key="fake", model=model, transport=_never)
        self._replies = list(replies)
        self.asked: List[str] = []

    @property
    def available(self) -> bool:
        return True

    def ask(self, system: str, user: str, **kw: Any) -> str:  # type: ignore[override]
        self.asked.append(user)
        if not self._replies:
            raise BrainError("剧本演完了")
        r = self._replies.pop(0)
        if callable(r):
            r = r(user)
        self.usage.add(len(user) // 4, 64)
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
    def _ask_raw(self, system: str, user: str, **kw: Any) -> tuple[str, str]:  # type: ignore[override]
        # 假脑子的回答天然完整，finish_reason 恒为 stop。
        # 通过 self.ask 取文本，好让子类只重写 ask 就能改变行为
        # （ask_json 走 _ask_raw，子类的 ask 覆盖才不会被绕过）。
        return self.ask(system, user, **kw), "stop"


def _never(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    raise BrainUnavailable("这是个假脑子，不该发出请求")
