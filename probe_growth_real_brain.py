"""用真实后台模型验证“人格是长出来的”最小实验。

用法（推荐走环境变量，避免 key 出现在 shell 历史里）：

  export LOAM_API_KEY='你的key'
  export LOAM_MODEL='你的flash模型ID'
  python /home/loam/probe_growth_real_brain.py

说明：
- 这个脚本不会把 key 写入仓库文件。
- 会强制要求模型名包含 flash（按你的测试约束）。
- 通过“先连续印证A，再连续印证B”的方式看两条种子特质强度如何随经历变化。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Dict, List

from loam.core.growth import Trait
from loam.mind.llm import Brain
from loam.server import LoamService, ServiceConfig


def _must_brain() -> Brain:
    api_key = os.environ.get("LOAM_API_KEY", "").strip()
    model = os.environ.get("LOAM_MODEL", "").strip()
    base = os.environ.get("LOAM_BASE_URL", "https://api.deepseek.com").strip()

    if not api_key:
        raise SystemExit("缺少 LOAM_API_KEY")
    if not model:
        raise SystemExit("缺少 LOAM_MODEL（必须是 flash 模型）")
    if "flash" not in model.lower():
        raise SystemExit(f"按约束只能用 flash 模型，当前 LOAM_MODEL={model!r}")

    return Brain(api_key=api_key, base_url=base, model=model)


def _ingest_cycle(service: LoamService, turn_base: int, style: str) -> None:
    """塞入一小段对话；style=direct|soothe。"""
    if style == "direct":
        a1 = "先不安慰，先把会议目标和风险列出来。"
        a2 = "你怕空白很正常，但先做两轮演练，比空想有效。"
    else:
        a1 = "先别急，我们先把紧张放下来，你已经很努力了。"
        a2 = "先照顾状态，再慢慢准备也可以。"

    service.ingest(
        {
            "session": "probe",
            "turns": [
                {"turn": turn_base, "role": "user", "content": "我明天要开会，很紧张。"},
                {"turn": turn_base, "role": "assistant", "content": a1},
                {"turn": turn_base + 1, "role": "user", "content": "我怕到时候脑子空白。"},
                {"turn": turn_base + 1, "role": "assistant", "content": a2},
            ],
        }
    )


def _strengths(service: LoamService) -> Dict[str, float]:
    by = {t.id: t for t in service.memory.load_traits(include_retired=True)}
    return {
        "direct": round(float(by.get("tr_direct", Trait(id="x", text="x")).strength), 4),
        "soothe": round(float(by.get("tr_soothe", Trait(id="x", text="x")).strength), 4),
    }


def main() -> int:
    brain = _must_brain()
    tmp = tempfile.mkdtemp(prefix="loam_probe_")
    print(f"[probe] data dir: {tmp}")

    svc = LoamService(
        ServiceConfig(character="probe", home=tmp, auto_start_grower=False, audit_every=0),
        brain=brain,
    )

    # 两条种子特质（相当于角色卡土壤）
    svc.memory.save_trait(
        Trait(id="tr_direct", text="我倾向于先拆事实和步骤，而不是先安抚"),
        from_seed=True,
    )
    svc.memory.save_trait(
        Trait(id="tr_soothe", text="我倾向于先安抚情绪，再进入问题"),
        from_seed=True,
    )

    trace: List[Dict[str, float]] = []

    try:
        turn = 1
        # 阶段A：连续“先拆步骤”
        for _ in range(6):
            _ingest_cycle(svc, turn, style="direct")
            r = svc.digest_once()
            s = _strengths(svc)
            s["cycle"] = float(r["周期"])
            trace.append(s)
            turn += 10

        # 阶段B：连续“先安抚”
        for _ in range(6):
            _ingest_cycle(svc, turn, style="soothe")
            r = svc.digest_once()
            s = _strengths(svc)
            s["cycle"] = float(r["周期"])
            trace.append(s)
            turn += 10

        print("\ncycle\tdirect\tsoothe")
        for row in trace:
            print(f"{int(row['cycle'])}\t{row['direct']:.4f}\t{row['soothe']:.4f}")

        st = svc.stats()
        print("\n[stats]")
        print(st)

        # 一个温和判据：至少出现可见变化（否则说明评判链路没打通）
        d0, d1 = trace[0]["direct"], trace[-1]["direct"]
        s0, s1 = trace[0]["soothe"], trace[-1]["soothe"]
        moved = abs(d1 - d0) + abs(s1 - s0)
        if moved < 0.03:
            print("\n⚠️ 变化很小：这通常是模型判定太保守，建议增加样本轮次到 20~30 周期")
        else:
            print("\n✅ 能看到强度随经历变化（不是写死角色卡）")
        return 0
    finally:
        svc.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())