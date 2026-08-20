"""L4 上下文装配测试。"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.core.growth import Trait
from loam.core.network import Network
from loam.mind.context import ContextBuilder, _estimate_tokens

from loam.store.memory import Event, Memory


def _event(eid: str, summary: str, salience: float = 0.5) -> Event:
    return Event(id=eid, summary=summary, source_ids=[1], salience=salience)


def test_context_includes_dossier_traits_and_narrative():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(_event("e1", "对方说明天要开会", 0.6))

        t = Trait(id="tr_1", text="我倾向于把话说明白", strength=0.72)
        t.evidence = ["e1"]
        m.save_trait(t)

        m.set_dossier("称呼", "阿萤", source_ids=["e1"])
        m.add_narrative("我大概是那种会把话说明白的人。", basis=["tr_1", "e1"], cycle=1)

        net = Network()
        net.add("e1", salience=0.6, anchor=True)
        m.save_network(net)

        pack = ContextBuilder(m).build("阿萤", "明天开会", learn=False)
        text = pack.render()

        assert pack.dossier.get("称呼") == "阿萤"
        assert pack.narrative
        assert any(ti["id"] == "tr_1" for ti in pack.traits)
        assert "[常驻档案]" in text and "[稳定倾向]" in text
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_context_recall_crosses_multi_hop_path():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(_event("e1", "对方提到明天季度汇报", 0.6))
        m.add_event(_event("e2", "上次汇报被领导打断", 0.7))
        m.add_event(_event("e3", "那次打断后对方脑子一片空白", 0.8))

        net = Network()
        net.add("e1", salience=0.6)
        net.add("e2", salience=0.7)
        net.add("e3", salience=0.8)
        net.link("e1", "e2", 0.65)
        net.link("e2", "e3", 0.7)
        m.save_network(net)

        pack = ContextBuilder(m, max_recall=10).build("阿萤", "明天汇报有点紧张", learn=False)
        ids = [x["id"] for x in pack.recalled]
        assert "e3" in ids, "应该能顺着路径召回 2 跳外的记忆"
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_context_without_query_still_returns_anchors():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(_event("e_anchor", "对方名字叫小雨", 0.9))

        net = Network()
        net.add("e_anchor", salience=0.9, anchor=True)
        m.save_network(net)

        pack = ContextBuilder(m).build("阿萤", "", learn=False)
        assert any(x["id"] == "e_anchor" and x["anchor"] for x in pack.recalled)
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_context_learn_strengthens_recalled_path():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(_event("e1", "对方说他明天要做季度汇报", 0.6))
        m.add_event(_event("e2", "上次汇报被打断让他更紧张", 0.7))

        net = Network()
        net.add("e1", salience=0.6)
        net.add("e2", salience=0.7)
        net.link("e1", "e2", 0.25)
        m.save_network(net)

        before = m.load_network().weight("e1", "e2")
        ContextBuilder(m).build("阿萤", "明天汇报", learn=True)
        after = m.load_network().weight("e1", "e2")
        assert after > before, "回忆本身应强化路径"
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_context_budget_respects_hard_limit():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")

        # 造一批长文本事件，确保会触发预算器裁剪。
        for i in range(1, 25):
            m.add_event(
                _event(
                    f"e{i}",
                    f"第{i}次关于明天开会和复盘的细节：" + ("要点很多，需要拆分计划。" * 8),
                    0.9,
                )
            )

        net = Network()
        for i in range(1, 25):
            net.add(f"e{i}", salience=0.8, anchor=(i <= 8))
        m.save_network(net)

        for i in range(1, 14):
            t = Trait(id=f"tr_{i}", text=(f"稳定倾向{i}：" + "先想清楚再回应。" * 6), strength=0.8)
            t.evidence = ["e1"]
            m.save_trait(t)

        for i in range(1, 13):
            m.set_dossier(f"字段{i}", "说明" + ("很长很长。" * 16), source_ids=["e1"])

        m.add_narrative("我最近一直在反复复盘。" * 120, basis=["tr_1", "e1"], cycle=1)

        pack = ContextBuilder(
            m,
            max_matches=16,
            max_recall=20,
            max_traits=12,
            soft_token_budget=220,
            hard_token_budget=260,
        ).build("阿萤", "明天开会", learn=False)

        assert pack.budget["estimated_tokens_after"] <= 260
        assert _estimate_tokens(pack.render()) <= 260
        assert pack.budget["estimated_tokens_before"] >= pack.budget["estimated_tokens_after"]
        assert pack.budget["trimmed"] is True
    finally:
        m.close()
        shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)