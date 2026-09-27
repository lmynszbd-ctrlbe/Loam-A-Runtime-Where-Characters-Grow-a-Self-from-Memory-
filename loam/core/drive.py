"""loam.core.drive: 蔡加尼克心理张力与内心执念系统 (Zeigarnik Effect & Latent Preoccupations).

人类心理学机制：
- 人类对已完成的事容易遗忘，对未闭环的困惑、未解决的冲突、悬而未决的关系记忆极深（Zeigarnik Effect）。
- 当一个事件带有强烈情感波动（valence 不为 0）或包含未解疑问（questions），在经历数个周期后若未得到化解，
  其内部心理张力（tension）会随时间上升，沉淀为角色的“内心执念/悬念”（Latent Preoccupation）。
- 执念是角色在剧场中产生“主动倾诉欲望”、“追问动机”和“戏剧阻力”的动力源泉。
- 当后续对话涉及该执念的主题，且角色得到了确定性反馈或释怀时，张力释放（Discharge），执念转化为“已释怀”历史。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Drive:
    """一条内心执念 / 未完成事件心结。"""

    id: str                           # 唯一 ID, 如 drv_1727439000_1
    theme: str                        # 执念主题/困惑 (如: "关于你提到的那次不告而别")
    source_event_id: str              # 触发该执念的原始事件 ID
    tension: float = 0.5              # 心理张力: 0.0 (微弱) ~ 1.0 (极度盘旋)
    questions: List[str] = field(default_factory=list)  # 盘旋在心中的具体疑问
    status: str = "active"            # "active" (盘旋中) | "resolved" (已释怀) | "faded" (自然淡忘)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolve_reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "theme": self.theme,
            "source_event_id": self.source_event_id,
            "tension": round(float(self.tension), 4),
            "questions": list(self.questions),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
            "resolve_reason": self.resolve_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Drive:
        return cls(
            id=str(data["id"]),
            theme=str(data.get("theme") or ""),
            source_event_id=str(data.get("source_event_id") or ""),
            tension=float(data.get("tension", 0.5)),
            questions=list(data.get("questions") or []),
            status=str(data.get("status") or "active"),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            resolved_at=float(data["resolved_at"]) if data.get("resolved_at") else None,
            resolve_reason=str(data.get("resolve_reason") or ""),
        )

    def escalate_tension(self, delta: float = 0.1) -> float:
        """随时间/周期未被解答，张力逐步发酵上升，最高 1.0。"""
        if self.status != "active":
            return self.tension
        self.tension = min(1.0, self.tension + delta)
        self.updated_at = time.time()
        return self.tension

    def discharge(self, reason: str = "") -> None:
        """得到回应或化解，张力释放并标记已释怀。"""
        self.status = "resolved"
        self.tension = 0.0
        self.resolved_at = time.time()
        self.resolve_reason = reason
        self.updated_at = time.time()
