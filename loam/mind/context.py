"""L4 上下文装配。

把 Memory 里的熟料拼成一次对话可直接喂给外部模型的上下文。
这一层不调用模型，只做检索、扩散、排序和格式化。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..core.network import seed_from_matches
from ..core.growth import Trait
from ..store.memory import Event, Memory


@dataclass
class ContextPack:
    """一次上下文装配的产物。"""

    character: str
    query: str
    cycle: int
    built_at: float

    dossier: Dict[str, str] = field(default_factory=dict)
    narrative: Optional[str] = None
    traits: List[Dict[str, object]] = field(default_factory=list)
    recalled: List[Dict[str, object]] = field(default_factory=list)
    matches: List[Dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "character": self.character,
            "query": self.query,
            "cycle": self.cycle,
            "built_at": self.built_at,
            "dossier": self.dossier,
            "narrative": self.narrative,
            "traits": self.traits,
            "recalled": self.recalled,
            "matches": self.matches,
        }

    def render(self) -> str:
        """给外部对话模型看的文本。"""
        lines: List[str] = []

        lines.append("[常驻档案]")
        if self.dossier:
            for k, v in sorted(self.dossier.items()):
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- （空）")

        if self.narrative:
            lines.append("\n[当前自述]")
            lines.append(self.narrative)

        lines.append("\n[稳定倾向]")
        if self.traits:
            for t in self.traits:
                lines.append(
                    f"- [{t['id']}] {t['text']} "
                    f"(强度 {float(t['strength']):.2f}, 来历 {int(t['evidence_count'])} 条)"
                )
        else:
            lines.append("- （还没有）")

        lines.append("\n[被想起的经历]")
        if self.recalled:
            for e in self.recalled:
                tags = []
                if e.get("anchor"):
                    tags.append("常驻")
                if e.get("stood_firm"):
                    tags.append("顶住压力")
                if e.get("score") is not None and not math.isinf(float(e["score"])):
                    tags.append(f"激活 {float(e['score']):.3f}")
                suffix = f"（{'，'.join(tags)}）" if tags else ""
                lines.append(f"- [{e['id']}] {e['summary']}{suffix}")
        else:
            lines.append("- （无）")

        if self.matches:
            lines.append("\n[字面命中（找门口）]")
            for m in self.matches:
                lines.append(
                    f"- [{m['id']}] score={float(m['score']):.3f} {m['summary']}"
                )

        return "\n".join(lines)


class ContextBuilder:
    """从熟料装配 L4 对话上下文。"""

    def __init__(
        self,
        memory: Memory,
        max_matches: int = 8,
        max_recall: int = 16,
        max_traits: int = 12,
        trait_floor: float = 0.2,
    ) -> None:
        self.memory = memory
        self.max_matches = max_matches
        self.max_recall = max_recall
        self.max_traits = max_traits
        self.trait_floor = trait_floor

    def build(self, character: str, query: str, learn: bool = True) -> ContextPack:
        net = self.memory.load_network()

        matches: List[Tuple[str, float]] = []
        if query.strip():
            matches = self.memory.search(query, limit=self.max_matches)

        seeds = seed_from_matches(matches, cap=self.max_matches)
        recalled_pairs = net.recall(seeds, limit=self.max_recall, learn=learn)

        # recall(learn=True) 会改变网络，记得回存
        if learn:
            self.memory.save_network(net)

        recalled_ids = [eid for eid, _ in recalled_pairs]
        recalled_events = self.memory.get_events(recalled_ids)
        by_id = {e.id: e for e in recalled_events}
        anchor_ids = set(net.anchors())

        recalled: List[Dict[str, object]] = []
        for eid, score in recalled_pairs:
            ev = by_id.get(eid)
            if ev is None:
                continue
            recalled.append(_event_view(ev, score=score, anchor=(eid in anchor_ids)))

        match_events = self.memory.get_events([eid for eid, _ in matches])
        match_by_id = {e.id: e for e in match_events}
        match_view: List[Dict[str, object]] = []
        for eid, score in matches:
            ev = match_by_id.get(eid)
            if ev is None:
                continue
            item = _event_view(ev, score=score, anchor=(eid in anchor_ids))
            match_view.append(item)

        traits = [
            _trait_view(t)
            for t in self.memory.load_traits()
            if t.strength >= self.trait_floor
        ][: self.max_traits]

        nar = self.memory.current_narrative(kind="derived")
        pack = ContextPack(
            character=character,
            query=query,
            cycle=int(self.memory.get_state("cycle", "0")),
            built_at=time.time(),
            dossier=self.memory.dossier(),
            narrative=(str(nar.get("text")) if nar else None),
            traits=traits,
            recalled=recalled,
            matches=match_view,
        )
        return pack


def _trait_view(t: Trait) -> Dict[str, object]:
    return {
        "id": t.id,
        "text": t.text,
        "strength": round(float(t.strength), 4),
        "evidence_count": len(t.evidence),
    }


def _event_view(e: Event, score: float, anchor: bool) -> Dict[str, object]:
    return {
        "id": e.id,
        "summary": e.summary,
        "salience": round(float(e.salience), 4),
        "stood_firm": bool(e.stood_firm),
        "anchor": anchor,
        "score": None if math.isinf(score) else round(float(score), 6),
    }
