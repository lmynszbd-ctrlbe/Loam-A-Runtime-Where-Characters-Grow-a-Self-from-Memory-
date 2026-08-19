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
from typing import Any, Callable, Dict, List, Optional


class BrainError(RuntimeError):
    """脑子没能给出可用的回答。"""


class BrainUnavailable(BrainError):
    """压根没配脑子 —— 没有 key，或者接口连不上。"""


#: 一次请求最多重试几次。后台任务不着急，宁可慢也别丢料。
RETRIES = 3

#: 重试的基础间隔（秒），每次翻倍。
BACKOFF = 2.0


@dataclass
class Usage:
    """花了多少 token。后台会跑很多次，这个得记着。"""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> Dict[str, int]:
        return {
            "调用次数": self.calls,
            "输入token": self.prompt_tokens,
            "输出token": self.completion_tokens,
            "合计": self.total,
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
    timeout: float = 120.0
    retries: int = RETRIES
    transport: Transport = http_transport
    usage: Usage = field(default_factory=Usage)

    #: 每次调用之后的回调，用于外部记账/打日志。
    on_call: Optional[Callable[[str, str], None]] = None

    @property
    def available(self) -> bool:
        return bool(self.api_key) or self.transport is not http_transport

    # ------------------------------------------------------------ 基本问答

    def ask(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """问一句，拿回文本。

        温度默认压得很低 —— 这不是创作，是审阅。同一批经历应该
        得出大致相同的结论，随机性在这里只会变成漂移。
        """
        if not self.available:
            raise BrainUnavailable(
                "还没配后台反思用的模型。把 key 写进 ~/.loam/secrets.json 的 api_key。"
            )

        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        payload: Dict[str, Any] = {
            "_api_key": self.api_key,
            "model": self.model,
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
                u = data.get("usage") or {}
                self.usage.add(
                    int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
                )
                if self.on_call:
                    self.on_call(user[:200], text[:200])
                return text
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
    ) -> Any:
        """问一句，要一段 JSON 回来。

        模型很爱在 JSON 外面裹 ```json 或者写几句解释，全都容忍掉。
        实在解析不出来，就重问一次并把错误告诉它。
        """
        prompt = user
        last: Optional[Exception] = None
        for _ in range(max(1, retries)):
            raw = self.ask(system, prompt, temperature=temperature, max_tokens=max_tokens)
            try:
                return parse_json(raw)
            except ValueError as exc:
                last = exc
                prompt = (
                    f"{user}\n\n上一次你的回答无法被解析：{exc}\n"
                    "只输出 JSON 本身，不要任何解释、不要代码块标记。"
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

    raise ValueError(f"不是 JSON：{text[:200]}")


# ---------------------------------------------------------------- 配置


SECRETS_NAME = "secrets.json"


def load_brain(home: str | Path = "~/.loam", **overrides: Any) -> Brain:
    """按 环境变量 > secrets.json > 默认值 的顺序装配脑子。

    secrets.json 永远不进仓库（.gitignore 里已经排掉）。
    没配 key 也不报错 —— 返回一个 available=False 的脑子，
    这样存储和内生机制依然能跑，只是不能煮料。
    """
    cfg: Dict[str, Any] = {}
    path = Path(home).expanduser() / SECRETS_NAME
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}

    key = os.environ.get("LOAM_API_KEY") or cfg.get("api_key", "")
    base = os.environ.get("LOAM_BASE_URL") or cfg.get("base_url") or "https://api.deepseek.com"
    model = os.environ.get("LOAM_MODEL") or cfg.get("model") or "deepseek-chat"

    brain = Brain(api_key=key, base_url=base, model=model)
    for k, v in overrides.items():
        setattr(brain, k, v)
    return brain


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


def _never(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    raise BrainUnavailable("这是个假脑子，不该发出请求")
