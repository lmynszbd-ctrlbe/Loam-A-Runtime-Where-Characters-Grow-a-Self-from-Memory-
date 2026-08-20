"""最小端到端验证：输入三次对话，第三次才触发特质值变化。"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.core.growth import Trait
from loam.mind import prompts
from loam.mind.llm import BrainError, ScriptedBrain
from loam.server import LoamService, ServiceConfig


def _ids_in(prompt: str) -> List[str]:
    return re.findall(r"\[(ev_[0-9_]+)\]", prompt)


class ThreeRoundBrain(ScriptedBrain):
    """按阶段返回固定结果，保证可复现。"""

    def __init__(self) -> None:
        super().__init__([])

    def ask(self, system: str, user: str, **kw: Any) -> str:  # type: ignore[override]
        self.asked.append(user)
        self.usage.add(len(user) // 4, 64)

        if system == prompts.EXTRACT_SYSTEM:
            out = [
                {
                    "summary": "对方持续为明天汇报做准备",
                    "questions": ["对方是否持续准备"],
                    "entities": ["汇报", "准备"],
                    "salience": 0.5,
                    "valence": 0.1,
                    "stood_firm": False,
                    "source_turns": [1],
                }
            ]
            return json.dumps(out, ensure_ascii=False)

        if system == prompts.APPRAISE_SYSTEM:
            ids = _ids_in(user)
            out = {
                "appraisals": [
                    {
                        "trait_id": "tr_prepare",
                        "event_id": ids[0] if ids else "",
                        "signal": 1.0,
                    }
                ],
                "proposals": [],
            }
            return json.dumps(out, ensure_ascii=False)

        if system == prompts.OBSERVE_SYSTEM:
            return "[]"

        if system == prompts.DOSSIER_SYSTEM:
            return "[]"

        if system == prompts.NARRATE_SYSTEM:
            return "我会先准备，再行动。"

        if system == prompts.DRIFT_SYSTEM:
            return json.dumps(
                {"lost": [], "drifted": [], "severity": 0.0, "note": "无"},
                ensure_ascii=False,
            )

        raise BrainError(f"unknown phase: {system}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="loam-verify-")
    try:
        svc = LoamService(
            ServiceConfig(
                character="验证角色",
                home=tmp,
                auto_start_grower=False,
                audit_every=0,
            ),
            brain=ThreeRoundBrain(),
        )

        # 预置一个待验证的特质，观察其在三次输入后的变化。
        svc.memory.save_trait(Trait(id="tr_prepare", text="我倾向于先准备再行动"))

        rounds: List[Dict[str, float | int]] = []
        for i in range(1, 4):
            ingest = svc.ingest(
                {
                    "session": "verify-s1",
                    "turns": [
                        {
                            "turn": i,
                            "role": "user",
                            "content": f"第{i}次输入：我继续准备明天汇报。",
                        }
                    ],
                }
            )
            report = svc.digest_once()
            trait = next((t for t in svc.memory.load_traits(include_retired=True) if t.id == "tr_prepare"), None)
            if trait is None:
                raise RuntimeError("trait tr_prepare disappeared")

            item = {
                "round": i,
                "added": int(ingest.get("added", 0)),
                "events": int(report.get("新事件", 0)),
                "strength": float(trait.strength),
                "pending": float(trait.pending),
            }
            rounds.append(item)
            print(
                f"round={item['round']} added={item['added']} events={item['events']} "
                f"strength={item['strength']:.6f} pending={item['pending']:.6f}"
            )

        strengths = [float(r["strength"]) for r in rounds]
        ok = abs(strengths[0]) < 1e-9 and abs(strengths[1]) < 1e-9 and strengths[2] > 0.0
        print(f"verdict={'PASS' if ok else 'FAIL'}")

        if not ok:
            return 1
        return 0
    finally:
        try:
            svc.close()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
