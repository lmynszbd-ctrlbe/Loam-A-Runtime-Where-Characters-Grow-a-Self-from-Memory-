"""存储层行为测试（Journal + Memory）。"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time

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

        loaded.gate_level = 2
        m.save_trait(loaded)
        loaded2 = [x for x in m.load_traits() if x.id == "tr_stage"][0]
        assert loaded2.gate_level == 2, "动态门槛等级要可持久化"
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_pending_ingest_queue_dedup_and_process():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        turns = [
            {"turn": 1, "role": "user", "content": "我明天要开会"},
            {"turn": 1, "role": "assistant", "content": "先列提纲"},
        ]

        first = j.enqueue_pending_evidence(c, "s1", turns)
        assert first["added"] == 2 and first["deduped"] == 0

        again = j.enqueue_pending_evidence(c, "s1", turns)
        assert again["added"] == 0 and again["deduped"] == 2

        out = j.process_one_ingest_job(c)
        assert out and out["done"] is True
        assert out["entries_added"] == 2
        assert j.pending_evidence_count(c) == 0
        assert len(j.read(c, session="s1")) == 2
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_queue_session_view_and_entries_lookup():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        j.enqueue_pending_evidence(c, "s1", [{"turn": 1, "role": "user", "content": "a"}])
        j.enqueue_pending_evidence(c, "s2", [{"turn": 1, "role": "user", "content": "b"}])

        sessions = j.queue_sessions(c, limit=10)
        assert len(sessions) >= 2
        assert {x["session"] for x in sessions} >= {"s1", "s2"}

        # 搬运一条后验证 entries_by_ids
        out = j.process_one_ingest_job(c)
        assert out and out["done"] is True
        rows = j.read(c, session=out["session"])  # type: ignore[index]
        looked = j.entries_by_ids([r.id for r in rows])
        assert len(looked) == len(rows)
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_recover_processing_jobs_to_pending():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        j.enqueue_pending_evidence(
            c,
            "s1",
            [{"turn": 1, "role": "user", "content": "一条证据"}],
        )

        claimed = j._claim_next_job(c)  # type: ignore[attr-defined]
        assert claimed is not None
        assert j.queue_stats(c)["jobs_processing"] == 1

        recovered = j.recover_processing_jobs(c)
        assert recovered == 1
        stats = j.queue_stats(c)
        assert stats["jobs_processing"] == 0
        assert stats["jobs_pending"] == 1
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_ingest_job_retries_then_failed():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        c = "阿萤"
        j.enqueue_pending_evidence(
            c,
            "s1",
            [{"turn": 1, "role": "user", "content": "会触发失败重试"}],
        )

        original = j.append_batch

        def boom(*_args, **_kwargs):
            raise RuntimeError("forced error")

        j.append_batch = boom  # type: ignore[assignment]

        r1 = j.process_one_ingest_job(c)
        assert r1 and r1["done"] is False and r1["retryable"] is True
        assert j.queue_stats(c)["jobs_pending"] == 1

        r2 = j.process_one_ingest_job(c)
        assert r2 and r2["done"] is False and r2["retryable"] is True
        assert j.queue_stats(c)["jobs_pending"] == 1

        r3 = j.process_one_ingest_job(c)
        assert r3 and r3["done"] is False and r3["retryable"] is False

        stats = j.queue_stats(c)
        assert stats["jobs_failed"] == 1
        assert stats["jobs_pending"] == 0
        assert stats["jobs_processing"] == 0
        assert j.pending_evidence_count(c) == 1

        j.append_batch = original  # type: ignore[assignment]
    finally:
        j.close()
        shutil.rmtree(tmp)


def test_runtime_config_version_and_rollback():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        v1 = m.set_runtime_config({"context.max_matches": 8}, note="init", actor="test")
        v2 = m.set_runtime_config({"context.max_matches": 5}, note="tune", actor="test")
        assert v2 > v1
        assert m.runtime_config().get("context.max_matches") == 5

        cfg = m.rollback_runtime_config(v1, note="rollback", actor="test")
        assert cfg.get("context.max_matches") == 8
        assert m.runtime_config().get("context.max_matches") == 8

        hist = m.runtime_config_history(limit=5)
        assert len(hist) >= 3
        assert hist[0]["config"].get("context.max_matches") == 8
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_event_decay_and_effective_salience():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        now = time.time()
        m.add_event(
            Event(
                id="e_old",
                summary="很久以前的普通事件",
                source_ids=[1],
                salience=1.0,
                happened_at=now - 8 * 3600,
            )
        )
        m.add_event(
            Event(
                id="e_firm",
                summary="很久以前但顶住压力的事件",
                source_ids=[2],
                salience=1.0,
                stood_firm=True,
                happened_at=now - 8 * 3600,
            )
        )

        m.apply_event_decay(half_life_hours=1.0, min_weight=0.2, stood_firm_floor=0.6, now=now)
        e_old = m.get_event("e_old")
        e_firm = m.get_event("e_firm")
        assert e_old and e_firm
        assert 0.19 <= e_old.salience <= 0.21, e_old.salience
        assert e_firm.salience >= 0.6, e_firm.salience
    finally:
        m.close()
        shutil.rmtree(tmp)


def test_time_window_aggregation_and_audit_tables():
    tmp = tempfile.mkdtemp()
    try:
        m = Memory(Path(tmp) / "memory.db")
        now = time.time()
        m.add_event(Event(id="e1", summary="最近1", source_ids=[1], salience=0.4, happened_at=now - 120))
        m.add_event(Event(id="e2", summary="最近2", source_ids=[2], salience=0.6, happened_at=now - 600))
        m.add_event(Event(id="e3", summary="很早", source_ids=[3], salience=0.8, happened_at=now - 4 * 3600))

        ws = m.event_window_stats(window_seconds=1800, bucket_seconds=300, now=now)
        assert sum(int(p["events"]) for p in ws["points"]) == 2
        assert "merged_points" in ws
        assert len(ws["merged_points"]) <= len(ws["points"])

        m.log_change(cycle=1, kind="trait_moved", reason="x", evidence=["e1"])
        m.log_change(cycle=1, kind="trait_moved", reason="y", evidence=["e2"])
        cs = m.changelog_window_stats(window_seconds=3600, bucket_seconds=300, now=now)
        assert sum(int(p["changes"]) for p in cs["points"]) >= 2

        eid = m.log_experiment_flags({"decay.enabled": True}, note="test", actor="tester")
        assert eid > 0
        exp = m.experiment_history(limit=1)
        assert exp and exp[0]["flags"].get("decay.enabled") is True

        rid = m.begin_recompute_run("incremental", trigger="test", from_cycle=1)
        m.finish_recompute_run(rid, status="ok", details={"reindexed": 3}, to_cycle=2)
        rh = m.recompute_history(limit=1)
        assert rh and rh[0]["status"] == "ok"
        assert rh[0]["details"].get("reindexed") == 3
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
