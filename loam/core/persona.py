"""性格宏观大旋钮 (Macro Persona Knobs) 与预设卡系统。

将 48 个底层物理常数抽象为 5 个直观气质维度与 4 套性格预设卡，
通过权重联动映射算法自动调节底层 overrides.json。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 5 个气质大旋钮定义 (取值范围 0.0 ~ 1.0，默认 0.5)
KNOBS_SCHEMA = {
    "sensitivity": {
        "name": "🌿 敏感度 / 易感性",
        "desc": "影响对微弱情绪信号的捕捉与波动强度（从钝感慢热到极度敏锐脆皮）",
        "default": 0.5,
    },
    "stubbornness": {
        "name": "🗿 沉稳度 / 执拗度",
        "desc": "影响特质成型后的稳固度与抗反驳能力（从随和变通到顽固不化）",
        "default": 0.5,
    },
    "resilience": {
        "name": "💧 自愈力 / 情绪消化",
        "desc": "影响情绪波动退散的速度与释怀效率（从持久内耗到迅速回血）",
        "default": 0.5,
    },
    "vigilance": {
        "name": "🛡️ 戒备度 / 多疑性",
        "desc": "影响信息入脑的信噪比门槛与反讽识别（从单纯直率到高防备警惕）",
        "default": 0.5,
    },
    "creativity": {
        "name": "✨ 联想力 / 脑洞发散",
        "desc": "影响记忆网络神经连线的扩散跨度与联想跳数（从单线程到发散脑补）",
        "default": 0.5,
    },
}

# 4 套开箱即用的一键性格预设卡
PRESET_PERSONAS: Dict[str, Dict[str, Any]] = {
    "aloof": {
        "name": "🧊 高冷孤傲",
        "desc": "慢热戒备，不易被日常琐事撼动，自愈极强，内心防线高耸",
        "knobs": {
            "sensitivity": 0.25,
            "stubbornness": 0.85,
            "resilience": 0.80,
            "vigilance": 0.85,
            "creativity": 0.35,
        },
    },
    "gentle": {
        "name": "🌸 温柔包容",
        "desc": "共情敏锐，自愈良好，低戒备心，富有丰富细腻的联想与理解力",
        "knobs": {
            "sensitivity": 0.75,
            "stubbornness": 0.30,
            "resilience": 0.70,
            "vigilance": 0.20,
            "creativity": 0.75,
        },
    },
    "cheerful": {
        "name": "🐶 乐天小狗",
        "desc": "超级易感，情绪来得快去得更快，毫无防备，永远充满探索热情",
        "knobs": {
            "sensitivity": 0.80,
            "stubbornness": 0.20,
            "resilience": 0.90,
            "vigilance": 0.10,
            "creativity": 0.60,
        },
    },
    "fragile": {
        "name": "🥀 敏感易碎",
        "desc": "极度敏感脆弱，内耗沉淀深，多疑防备，脑补发散强烈",
        "knobs": {
            "sensitivity": 0.90,
            "stubbornness": 0.40,
            "resilience": 0.15,
            "vigilance": 0.80,
            "creativity": 0.85,
        },
    },
}


def map_knobs_to_constants(knobs: Dict[str, float]) -> Dict[str, float]:
    """将 5 个 0.0~1.0 的气质旋钮值，通过数学阻尼曲线映射到 48 个底层常数。"""
    s = max(0.0, min(1.0, float(knobs.get("sensitivity", 0.5))))
    st = max(0.0, min(1.0, float(knobs.get("stubbornness", 0.5))))
    r = max(0.0, min(1.0, float(knobs.get("resilience", 0.5))))
    v = max(0.0, min(1.0, float(knobs.get("vigilance", 0.5))))
    c = max(0.0, min(1.0, float(knobs.get("creativity", 0.5))))

    overrides: Dict[str, float] = {}

    # 1. 敏感度 s: 推动力(0.18~0.55), 突破门槛反向(0.95~0.70), 快态上限(0.15~0.42)
    overrides["PLASTICITY"] = round(0.18 + 0.37 * s, 4)
    overrides["BREAKTHROUGH"] = round(0.95 - 0.25 * s, 4)
    overrides["FAST_LIMIT"] = round(0.15 + 0.27 * s, 4)

    # 2. 执拗度 st: 天花板(0.90~0.99), 衰减半衰期长(0.995~0.9999), 门槛增益(1.02~1.35)
    overrides["CEILING"] = round(0.90 + 0.09 * st, 4)
    overrides["DECAY"] = round(0.995 + 0.0049 * st, 5)
    overrides["GATE_LEVEL_MULTIPLIER"] = round(1.02 + 0.33 * st, 3)

    # 3. 自愈力 r: 快态消退速度(0.85~0.45 越小退越快), 渗漏速度(0.80~0.98), 残留(0.35~0.05)
    overrides["FAST_DECAY"] = round(0.85 - 0.40 * r, 4)
    overrides["LEAK"] = round(0.98 - 0.18 * r, 4)
    overrides["PENDING_RESIDUAL"] = round(0.35 - 0.30 * r, 4)

    # 4. 戒备度 v: 入脑置信度(0.35~0.75), 反讽阈值(0.88~0.50)
    overrides["UNCERTAINTY_GATE"] = round(0.35 + 0.40 * v, 4)
    overrides["SARCASTIC_AMBIGUITY"] = round(0.88 - 0.38 * v, 4)

    # 5. 联想力 c: 神经扩散衰减(0.60~0.88), 最大跳数(2~6), 连线强化(0.15~0.50)
    overrides["SPREAD_DECAY"] = round(0.60 + 0.28 * c, 4)
    overrides["MAX_HOPS"] = int(round(2 + 4 * c))
    overrides["EDGE_STRENGTHEN"] = round(0.15 + 0.35 * c, 4)

    return overrides
