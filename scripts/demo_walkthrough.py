#!/usr/bin/env python3
"""demo_walkthrough.py — 终端快速演化沙盒演示 (零 API 成本)

演示 loam 核心机制：
1. 消息摄入三通道分流 (Thought / Action / Dialogue)
2. 经历如何进入 L0 矿床与 L1 事件
3. 门控蓄水池 (Pending Gating) 如何驱动特质质变
4. 赫布神经突触网络与原矿精准下钻 (L0 Raw Drilldown)
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loam.core.growth import Trait, Evidence
from loam.core.network import Network
from loam.core.persona import map_knobs_to_constants, PRESET_PERSONAS
from loam.core.resonance import EmotionalResonanceEngine
from loam.mind.context import ContextBuilder
from loam.mind.pipeline import parse_turn_channels
from loam.store.journal import Journal
from loam.store.memory import Event, Memory


def print_step(title: str) -> None:
    print(f"\n\033[1;36m{'='*15} {title} {'='*15}\033[0m")


def main() -> None:
    print("\033[1;32m🌱 欢迎来到 loam 核心生命力推演沙盒 (Demo Walkthrough)!\033[0m")
    time.sleep(0.5)

    # 1. 消息三通道分流管道
    print_step("Step 1: 消息三通道管道分流 (Thought/Dialogue/Action)")
    sample_msg = (
        "<think>检测到主人今天工作很不顺利，我应该收起平时的调皮，认真安慰。</think>"
        "辛苦啦！无论今天遇到什么烦心事，回到家这里就是最温暖的港湾～"
        "<tool_call>{\"action\": \"play_comfort_music\", \"mood\": \"relax\"}</tool_call>"
    )
    print(f"📥 原始入库消息:\n   {sample_msg}\n")
    parsed = parse_turn_channels("assistant", sample_msg)
    print(f"🧠 [Thought 通道 - 瞬态思考, 不污染回忆]:\n   ↳ {parsed.thought}")
    print(f"💬 [Dialogue 通道 - 纯净对话, 沉淀为性格]:\n   ↳ {parsed.dialogue}")
    print(f"🛠️ [Action 通道 - 工具意图, 挂载为语义]:\n   ↳ {parsed.actions}")
    time.sleep(0.8)

    # 2. 五行生克与情绪共振
    print_step("Step 2: 情绪动力学 (五行生克与阻尼引擎)")
    res_engine = EmotionalResonanceEngine()
    print("🔥 注入一次热情/开朗脉冲 (Fire +0.8)...")
    snap1 = res_engine.pulse("fire", 0.8, note="开心的对话")
    print(f"   ↳ 能量分布: {snap1} (火生土，土能量被顺势激发)")
    print("💧 注入一次警惕/担忧脉冲 (Water +0.7)...")
    snap2 = res_engine.pulse("water", 0.7, note="察觉到风险")
    print(f"   ↳ 能量分布: {snap2} (水克火，火能量被阻尼平抑)")
    mood, energy = res_engine.dominant_mood()
    print(f"   🎭 当前主导情绪态: [{mood}] 强度: {energy:.2f}")
    time.sleep(0.8)

    # 3. 门控蓄水池与特质质变
    print_step("Step 3: 门控蓄水池 (Pending Gating & Qualitative Shift)")
    trait = Trait(id="tr_empathy", text="温柔体贴，善于抚慰他人情绪", strength=0.2)
    print(f"🌱 初始特质: [{trait.text}] 初始强度: {trait.strength:.2f}")
    print("🌊 连续经历 3 次重大抚慰事件，向蓄水池注入证据...")
    for i in range(1, 4):
        ev = Evidence(
            event_id=f"ev_care_{i}",
            signal=1.0,
            salience=0.85,
            confidence=0.9,
            ambiguity=0.1,
        )
        trait.feed(ev)
        print(f"   第 {i} 次事件注入 -> 蓄水池 pending: {trait.pending:.4f}, 动态门槛: {trait.gate:.4f}")
    
    # 模拟周期结算 (Settle)
    shift = trait.settle()
    print(f"✨ 突破动态门槛！发生质变 (Shift): +{shift:.4f} -> 最终特质强度: {trait.strength:.4f}")
    time.sleep(0.8)

    # 4. 原矿精准下钻 (L0 Raw Drilldown)
    print_step("Step 4: 记忆网络与 L0 原矿下钻装配 (Context Assembly)")
    tmp_dir = tempfile.mkdtemp()
    j_path = Path(tmp_dir) / "demo_j.db"
    m_path = Path(tmp_dir) / "demo_m.db"
    journal = Journal(j_path)
    memory = Memory(m_path)

    eid1 = journal.append("小猫", "sess_001", 1, "user", "今天加班到好晚，项目终于上线了！")
    eid2 = journal.append("小猫", "sess_001", 2, "assistant", "哇！辛苦啦，今晚一定要好好睡一觉！")

    memory.add_event(
        Event(
            id="ev_launch_success",
            summary="主人项目顺利上线，深夜互相庆祝并叮嘱休息",
            source_ids=[eid1, eid2],
            salience=0.9,
            session="sess_001",
        )
    )
    net = Network()
    net.add("ev_launch_success", salience=0.9, anchor=True)
    memory.save_network(net)

    builder = ContextBuilder(memory=memory, journal=journal, drilldown_top_k=1)
    pack = builder.build("小猫", query="项目上线", learn=True)
    print("📜 装配输出的模型实时认知上下文 (Rendered Context):")
    print("-" * 50)
    print(pack.render())
    print("-" * 50)

    journal.close()
    memory.close()
    print("\n\033[1;32m🎉 演示完成！loam 的所有生命力特性均已生效且可自由扩展！\033[0m\n")


if __name__ == "__main__":
    main()
