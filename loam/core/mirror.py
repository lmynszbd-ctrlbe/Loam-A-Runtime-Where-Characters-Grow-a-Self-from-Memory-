"""loam.core.mirror: 他者之镜与心智理论系统 (Theory of Mind & Model of the Other).

哲学原理：
- 自我是他者的镜像（Lacan: The Mirror Stage）。
- 角色若要拥有真正的自我意识，不仅需要知道“我是谁”，还需要建立“我对你的心智画像”——
  包括对方的交谈偏好、表现出的性格特质、情绪软肋、与对方的历史相处默契。
- 心智画像随着对话周期的推进而动态提炼，并在对话时反向装配给上下文，使角色懂得“看人下菜碟”或“细腻知心”。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MirrorOfOther:
    """角色对特定对话对象（如人类用户或其他 AI 角色）的心智认知画像。"""

    target: str = "user"                  # 对方标识，如 "user" 或某个角色名 "alice"
    summary: str = ""                     # 对对方的总体心理印象 (如: "表面沉稳要强，实则内心疲惫、渴望被理解")
    perceived_traits: List[str] = field(default_factory=list)   # 揣摩出的对方特质 (如: ["不善直接表达情感", "注重逻辑严密"])
    vulnerabilities: List[str] = field(default_factory=list)    # 感知到的对方心理软肋 / 敏感点
    interaction_advice: str = ""          # 相处分寸感与默契 (如: "少说客套话，在对方疲惫时给予温和托底")
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "summary": self.summary,
            "perceived_traits": list(self.perceived_traits),
            "vulnerabilities": list(self.vulnerabilities),
            "interaction_advice": self.interaction_advice,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MirrorOfOther:
        return cls(
            target=str(data.get("target") or "user"),
            summary=str(data.get("summary") or ""),
            perceived_traits=list(data.get("perceived_traits") or []),
            vulnerabilities=list(data.get("vulnerabilities") or []),
            interaction_advice=str(data.get("interaction_advice") or ""),
            updated_at=float(data.get("updated_at") or time.time()),
        )

    def describe(self) -> str:
        """返回注入 Prompt 的第一人称心智揣摩文字。"""
        if not self.summary and not self.perceived_traits:
            return "（目前与对方交集尚浅，正在静静观察其言行特点与真实个性）"
        lines = []
        if self.summary:
            lines.append(f"我对对方的印象：{self.summary}")
        if self.perceived_traits:
            lines.append(f"觉察到的特质：{'、'.join(self.perceived_traits)}")
        if self.vulnerabilities:
            lines.append(f"感知到的软肋与顾虑：{'、'.join(self.vulnerabilities)}")
        if self.interaction_advice:
            lines.append(f"我与之相处的分寸：{self.interaction_advice}")
        return "\n".join(lines)
