"""loam.mind.pipeline: 消息输入管道与三通道分流 (Thought / Dialogue / Action)。

在消息摄入时将内容结构化解析为不同通道：
- thought: 思考过程 / 内心戏（只参与短时状态，不写入 L0 永久记忆，避免回忆污染）
- dialogue: 真实交流对话（落盘 L0 原矿 entries，进入情景记忆与性格沉淀）
- action: 工具调用 / 动作意图（提炼语义，挂载到记忆节点中）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


_THINK_RE = re.compile(r"<think(?:ing)?>([\s\S]*?)</think(?:ing)?>", re.IGNORECASE)
_TOOL_CALL_RE = re.compile(r"<tool_call>([\s\S]*?)</tool_call>", re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)


@dataclass
class ChannelSegment:
    """单个通道分段。"""
    channel: str  # "thought" | "dialogue" | "action"
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTurn:
    """单轮消息三通道解析结果。"""
    role: str
    raw_content: str
    thought: str = ""
    dialogue: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    segments: List[ChannelSegment] = field(default_factory=list)

    @property
    def has_dialogue(self) -> bool:
        return bool(self.dialogue.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "raw_content": self.raw_content,
            "thought": self.thought,
            "dialogue": self.dialogue,
            "actions": self.actions,
        }


def parse_turn_channels(role: str, content: str) -> ParsedTurn:
    """将一条消息解析为 Thought / Dialogue / Action 三通道。"""
    raw = str(content or "")
    if not raw.strip():
        return ParsedTurn(role=role, raw_content=raw)

    thought_parts: List[str] = []
    actions: List[Dict[str, Any]] = []
    segments: List[ChannelSegment] = []

    # 1. 抽取 <think>...</think>
    def _extract_think(match: re.Match) -> str:
        th = match.group(1).strip()
        if th:
            thought_parts.append(th)
            segments.append(ChannelSegment(channel="thought", content=th))
        return ""

    residual = _THINK_RE.sub(_extract_think, raw)

    # 2. 抽取 <tool_call>...</tool_call>
    def _extract_tool(match: re.Match) -> str:
        tc = match.group(1).strip()
        if tc:
            try:
                parsed = json.loads(tc)
                actions.append(parsed if isinstance(parsed, dict) else {"raw": tc})
            except Exception:
                actions.append({"raw": tc})
            segments.append(ChannelSegment(channel="action", content=tc, meta={"type": "xml_tool_call"}))
        return ""

    residual = _TOOL_CALL_RE.sub(_extract_tool, residual)

    # 3. 检查残留文本中的独立 JSON tool call 代码块
    for jm in _JSON_BLOCK_RE.finditer(residual):
        block_text = jm.group(1).strip()
        try:
            val = json.loads(block_text)
            if isinstance(val, dict) and ("tool" in val or "tool_name" in val or "action" in val or "name" in val):
                actions.append(val)
                segments.append(ChannelSegment(channel="action", content=block_text, meta={"type": "json_block"}))
        except Exception:
            pass

    # 4. 剩余文本即为纯净的对外对话
    clean_dialogue = residual.strip()
    if clean_dialogue:
        segments.append(ChannelSegment(channel="dialogue", content=clean_dialogue))

    full_thought = "\n\n".join(thought_parts).strip()

    return ParsedTurn(
        role=role,
        raw_content=raw,
        thought=full_thought,
        dialogue=clean_dialogue,
        actions=actions,
        segments=segments,
    )


def sanitize_turns_for_ingest(turns: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """对即将入库的 turns 进行通道分流过滤与元数据挂载。
    - thought 剥离到 meta 中（不污染 entries.content 对话）
    - action 意图提炼到 meta['actions'] 中
    - content 仅保留对话主干
    """
    sanitized: List[Dict[str, Any]] = []
    stats = {"total": len(turns), "filtered_dialogue": 0, "has_thought": 0, "has_action": 0}

    for t in turns:
        role = str(t.get("role") or "").strip()
        content = str(t.get("content") or "")
        parsed = parse_turn_channels(role, content)

        if parsed.thought:
            stats["has_thought"] += 1
        if parsed.actions:
            stats["has_action"] += 1

        # 若经过过滤后存在有效对话，或本身是用户输入
        clean_text = parsed.dialogue if parsed.dialogue else (content if role.lower() == "user" else "")
        if not clean_text.strip():
            continue

        item = dict(t)
        item["content"] = clean_text
        meta = dict(item.get("meta") or {})
        if parsed.thought:
            meta["thought_preview"] = parsed.thought[:200]
        if parsed.actions:
            meta["actions"] = parsed.actions
        item["meta"] = meta
        sanitized.append(item)
        stats["filtered_dialogue"] += 1

    return sanitized, stats
