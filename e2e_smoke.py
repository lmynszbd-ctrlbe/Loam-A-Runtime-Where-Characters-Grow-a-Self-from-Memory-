"""本地端到端冒烟脚本（不需要 API key）。

运行：
    python /home/loam/e2e_smoke.py
"""

from __future__ import annotations

import json
import shutil
import tempfile

from loam.mind.llm import ScriptedBrain
from loam.server import LoamService, ServiceConfig


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="loam_smoke_")
    print(f"[loam-smoke] data dir: {tmp}")

    # extract / appraise / dossier 三步
    brain = ScriptedBrain(
        [
            [
                {
                    "summary": "对方说明天开会有点紧张",
                    "questions": ["对方最近为什么紧张"],
                    "entities": ["开会"],
                    "salience": 0.6,
                    "valence": -0.2,
                    "stood_firm": False,
                    "source_turns": [1],
                }
            ],
            {"appraisals": [], "proposals": []},
            [],
        ]
    )

    svc = LoamService(
        ServiceConfig(character="demo", home=tmp, auto_start_grower=False, audit_every=0),
        brain=brain,
    )

    try:
        ing = svc.ingest(
            {
                "session": "demo-session",
                "turns": [
                    {"turn": 1, "role": "user", "content": "我明天要开会，有点紧张"},
                    {"turn": 1, "role": "assistant", "content": "我们来拆一下准备步骤"},
                ],
            }
        )
        print("\n[ingest]")
        print(json.dumps(ing, ensure_ascii=False, indent=2))

        rep = svc.digest_once()
        print("\n[digest_once]")
        print(json.dumps(rep, ensure_ascii=False, indent=2))

        ctx = svc.build_context("明天开会", learn=False)
        print("\n[context.text]\n")
        print(ctx["text"])

        st = svc.stats()
        print("\n[stats]")
        print(json.dumps(st, ensure_ascii=False, indent=2))

        print("\n✅ smoke ok")
        return 0
    finally:
        svc.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())