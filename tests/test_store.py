"""存储层行为测试（Journal + Memory）。"""

from __future__ import annotations

import shutil
import sys
import tempfile

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.core.growth import Evidence, Trait
from loam.core.network import Network
from loam.store import Event, Journal, Memory


def test_journal_append_dedup_and_read_order():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        i1 = j.append(c, "s1", 1, "user", "你好")
        i2 = j.append(c, "s1", 1, "user", "你好")  # 指纹重复
        assert i1 is not None
        assert i2 is None, "重复补录应该被去重"

        rows = j.read(c)
        assert [r.turn for r in rows] == [1]
        assert rows[0].content == "你好"
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_journal_gap_detect_and_reconcile():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"

        assert j.observe_turn(c, "s1", 1) is None
        gap = j.observe_turn(c, "s1", 3)
        assert gap == (2, 2)
        assert len(j.open_gaps(c)) == 1

        j.append(c, "s1", 1, "user", "第1轮")
        j.append(c, "s1", 3, "user", "第3轮")
        j.append_batch(c, "s1", [{"turn": 2, "role": "user", "content": "补第2轮"}])

        assert j.reconcile_gaps(c) == 1
        assert len(j.open_gaps(c)) == 0
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_journal_reset_digestion_roundtrip():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        ids = []
        for t in (1, 2, 3):
            ids.append(j.append(c, "s1", t, "user", f"第{t}轮") or 0)

        j.mark_digested(ids[:2])
        assert j.stats(c)["已消化"] == 2

        n = j.reset_digestion(c)
        assert n == 3
        assert j.stats(c)["已消化"] == 0
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_memory_event_requires_source_ids():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        try:
            m.add_event(Event(id="e1", summary="无根事件", source_ids=[]))
            raise AssertionError("无来历事件应当被拒绝")
        except ValueError:
            pass
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_memory_chinese_search_hits_questions_and_entities():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(
            Event(
                id="e1",
                summary="对方提到上次汇报被领导打断",
                source_ids=[1],
                questions=["对方为什么怕开会"],
                entities=["汇报", "领导"],
                salience=0.7,
            )
        )
        hits = m.search("我明天开会有点紧张", limit=5)
        assert hits, "query 应该能命中 questions/summary"
        assert hits[0][0] == "e1"
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_memory_wipe_derived_keeps_ledger_and_narrative():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        m.add_event(Event(id="e1", summary="发生了一件事", source_ids=[1], salience=0.6))

        t = Trait(id="tr_1", text="我倾向于直说")
        t.feed(Evidence(event_id="e1", signal=1.0, salience=0.6))
        m.save_trait(t)

        net = Network()
        net.add("e1", salience=0.6)
        m.save_network(net)

        m.add_narrative("一版自述", basis=["e1"], cycle=1)
        m.log_change(cycle=1, kind="test", reason="留账", evidence=["e1"])

        m.wipe_derived()

        assert m.stats()["事件"] == 0
        assert m.stats()["特质"] == 0
        assert len(m.history()) >= 1, "账本不能清"
        assert len(m.narrative_history()) >= 1, "自述历史不能清"
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_trait_staged_roundtrip_via_memory():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        t = Trait(id="tr_stage", text="我倾向于先观察")
        t.feed(Evidence(event_id="e1", signal=0.3, salience=0.2))
        # 不足以过阈值：停留在蓄水池
        t.settle(now="c1")
        m.save_trait(t)

        loaded = [x for x in m.load_traits() if x.id == "tr_stage"][0]
        assert loaded.pending > 0
        assert loaded._staged, "蓄水池来历要可持久化"
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
