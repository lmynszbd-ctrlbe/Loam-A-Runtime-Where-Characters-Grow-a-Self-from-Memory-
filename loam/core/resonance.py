"""loam.core.resonance: 五行生克与情绪共振阻尼矩阵。

将情绪/性格状态建模为互相制约与促进的共振系统（类似金木水火土生克循环或多元情绪动力学）：
- 生（Reinforce / Generate）：喜生乐、安生信、思生定
- 克（Inhibit / Dampen）：怒克静、惧克勇、躁克稳
- 阻尼衰减与滑动窗口（Sliding Window Resonance）：短期情绪起伏在窗口内产生阻尼回荡，避免情绪断崖突变或无休止失控。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# 基础情绪特质映射表 (五行情志模型)
# 木(怒/进取) -> 火(喜/热情) -> 土(思/深沉) -> 金(忧/秩序) -> 水(恐/警惕) -> 木
GENERATIVE_CYCLE = {
    "wood": "fire",      # 进取/生长 激发 热情
    "fire": "earth",     # 热情 沉淀为 深思
    "earth": "metal",    # 深思 凝结为 秩序/敏锐
    "metal": "water",    # 秩序/收敛 转化为 警惕/清冷
    "water": "wood",     # 警惕/蓄势 催生 进取
}

OVERCOMING_CYCLE = {
    "wood": "earth",     # 进取 破除 凝滞深沉 (木克土)
    "earth": "water",    # 深沉 吸收 恐惧警惕 (土克水)
    "water": "fire",     # 警惕 浇灭 狂热躁动 (水克火)
    "fire": "metal",     # 热情 融化 冰冷秩序 (火克金)
    "metal": "wood",     # 秩序 裁剪 盲目进取 (金克木)
}


@dataclass
class EmotionPulse:
    """单次情绪波动脉冲。"""
    element: str          # "wood" | "fire" | "earth" | "metal" | "water"
    intensity: float      # [-1.0, 1.0]
    timestamp: float = field(default_factory=time.time)
    note: str = ""


class EmotionalResonanceEngine:
    """情绪共振与生克阻尼引擎。"""

    def __init__(
        self,
        window_size: int = 10,
        damping_factor: float = 0.85,
        resonance_gain: float = 0.15,
    ) -> None:
        self.window_size = max(3, int(window_size))
        self.damping_factor = min(0.99, max(0.1, float(damping_factor)))
        self.resonance_gain = min(0.5, max(0.01, float(resonance_gain)))
        self.history: List[EmotionPulse] = []
        self._states: Dict[str, float] = {
            "wood": 0.0,
            "fire": 0.0,
            "earth": 0.0,
            "metal": 0.0,
            "water": 0.0,
        }

    def pulse(self, element: str, intensity: float, note: str = "") -> Dict[str, float]:
        """注入一次情绪脉冲，触发五行生克共振与阻尼演化。"""
        elem = element.lower().strip()
        if elem not in self._states:
            elem = "wood"

        val = max(-1.0, min(1.0, float(intensity)))
        p = EmotionPulse(element=elem, intensity=val, note=note)
        self.history.append(p)
        if len(self.history) > self.window_size * 2:
            self.history = self.history[-self.window_size :]

        # 1. 基础阻尼衰减
        for k in self._states:
            self._states[k] *= self.damping_factor

        # 2. 注入当前脉冲
        self._states[elem] += val

        # 3. 生克链式传导
        target_gen = GENERATIVE_CYCLE.get(elem)
        target_over = OVERCOMING_CYCLE.get(elem)

        if target_gen and val > 0:
            # 相生：同向轻微促进
            self._states[target_gen] += val * self.resonance_gain
        elif target_gen and val < 0:
            self._states[target_gen] += val * self.resonance_gain * 0.5

        if target_over and val > 0:
            # 相克：正向能量抑制相克方
            self._states[target_over] -= val * self.resonance_gain * 0.8
        elif target_over and val < 0:
            # 自身虚弱时，被克方反弹
            self._states[target_over] += abs(val) * self.resonance_gain * 0.4

        # 归一化限制
        for k in self._states:
            self._states[k] = max(-1.0, min(1.0, self._states[k]))

        return self.get_resonance_snapshot()

    def get_resonance_snapshot(self) -> Dict[str, float]:
        """获取当前情绪能量分布。"""
        return {k: round(v, 4) for k, v in self._states.items()}

    def dominant_mood(self) -> Tuple[str, float]:
        """获取当前占主导的情绪态及其能量。"""
        best_elem = "wood"
        max_energy = -999.0
        for elem, val in self._states.items():
            if abs(val) > max_energy:
                max_energy = abs(val)
                best_elem = elem
        return best_elem, self._states[best_elem]

    def to_dict(self) -> Dict[str, Any]:
        """序列化引擎状态，用于跨周期持久化。"""
        return {
            "window_size": self.window_size,
            "damping_factor": self.damping_factor,
            "resonance_gain": self.resonance_gain,
            "states": {k: round(v, 4) for k, v in self._states.items()},
            "history": [
                {
                    "element": p.element,
                    "intensity": p.intensity,
                    "timestamp": p.timestamp,
                    "note": p.note,
                }
                for p in self.history[-self.window_size :]
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EmotionalResonanceEngine:
        """从字典反序列化还原引擎状态。"""
        engine = cls(
            window_size=data.get("window_size", 10),
            damping_factor=data.get("damping_factor", 0.85),
            resonance_gain=data.get("resonance_gain", 0.15),
        )
        if "states" in data and isinstance(data["states"], dict):
            for k, v in data["states"].items():
                if k in engine._states:
                    try:
                        engine._states[k] = max(-1.0, min(1.0, float(v)))
                    except (ValueError, TypeError):
                        pass
        if "history" in data and isinstance(data["history"], list):
            for item in data["history"]:
                if isinstance(item, dict) and "element" in item and "intensity" in item:
                    engine.history.append(
                        EmotionPulse(
                            element=str(item["element"]),
                            intensity=float(item["intensity"]),
                            timestamp=float(item.get("timestamp", time.time())),
                            note=str(item.get("note", "")),
                        )
                    )
        return engine

    def describe_mood(self) -> str:
        """输出可直读的情绪与心境自然语言描述（用于上下文注入）。"""
        elem, val = self.dominant_mood()
        if abs(val) < 0.15:
            return "心绪平和：当前处于均衡松弛状态，无剧烈情绪起伏。"

        meta = ELEMENT_META.get(
            elem,
            {"name": elem, "positive": "活跃", "negative": "低落", "quality": "常态"},
        )
        tone = meta["positive"] if val > 0 else meta["negative"]
        level = "充沛强烈" if abs(val) > 0.65 else ("明显" if abs(val) > 0.35 else "微澜")
        return f"{meta['name']}气·{tone}（能量等级：{level}，当前强度：{val:+.2f}）。心智特质偏向【{meta['quality']}】。"

    def mood_snapshot(self) -> Dict[str, Any]:
        """返回结构化心境快照。"""
        elem, val = self.dominant_mood()
        return {
            "dominant_element": elem,
            "dominant_intensity": round(val, 4),
            "description": self.describe_mood(),
            "elements": self.get_resonance_snapshot(),
        }


ELEMENT_META: Dict[str, Dict[str, str]] = {
    "wood": {"name": "木", "positive": "进取活跃", "negative": "烦闷躁动", "quality": "生发突破"},
    "fire": {"name": "火", "positive": "热情开朗", "negative": "焦虑急躁", "quality": "喜悦共鸣"},
    "earth": {"name": "土", "positive": "笃定沉稳", "negative": "凝滞迟缓", "quality": "包容深思"},
    "metal": {"name": "金", "positive": "清醒决断", "negative": "清冷戒备", "quality": "秩序边界"},
    "water": {"name": "水", "positive": "柔和变通", "negative": "不安疑虑", "quality": "内敛敏锐"},
}

