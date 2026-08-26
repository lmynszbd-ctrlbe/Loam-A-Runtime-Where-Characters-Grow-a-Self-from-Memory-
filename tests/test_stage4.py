"""测试第四阶段：五行生克与情绪共振阻尼矩阵。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loam.core.resonance import EmotionalResonanceEngine


def test_resonance_generative_and_overcoming() -> None:
    engine = EmotionalResonanceEngine(damping_factor=0.9, resonance_gain=0.2)

    # 1. 注入火脉冲（热情 / 喜悦），应生土（思），克金（秩序/冰冷）
    state = engine.pulse("fire", 0.8, note="开心的对话")
    assert state["fire"] > 0.5
    assert state["earth"] > 0, "火生土：土能量应当被激发"
    assert state["metal"] < 0, "火克金：金能量应当被抑制"
    print("  PASS test_resonance_generative_and_overcoming: fire pulse ok")

    # 2. 注入水脉冲（警惕 / 恐惧），应克火（热情），生木（进取）
    state2 = engine.pulse("water", 0.9, note="被突发事件吓到")
    assert state2["water"] > 0.5
    assert state2["fire"] < state["fire"], "水克火：火能量被明显削弱"
    print("  PASS test_resonance_generative_and_overcoming: water pulse dampens fire")


def test_resonance_dominant_mood() -> None:
    engine = EmotionalResonanceEngine()
    engine.pulse("metal", 0.7, note="进入严谨反思模式")
    elem, energy = engine.dominant_mood()
    assert elem == "metal"
    assert energy > 0.5
    print("  PASS test_resonance_dominant_mood")


if __name__ == "__main__":
    test_resonance_generative_and_overcoming()
    test_resonance_dominant_mood()
    print("All fourth stage tests passed!")