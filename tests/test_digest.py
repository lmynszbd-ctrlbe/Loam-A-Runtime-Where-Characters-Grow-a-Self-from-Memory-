"""消化循环的行为测试。

全部离线跑 —— 用假脑子顶替真模型。所以这些测试断言的是
"链路对不对""闸门关不关得住"，不依赖任何 key，也不花钱。

真模型的判断质量另说，那个只能等有 key 之后实测。
"""

from __future__ import annotations
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from loam.core.growth import BREAKTHROUGH, Evidence, Trait
from loam.mind import prompts
from loam.mind.digest import Digester, Grower
from loam.mind.llm import Brain, BrainError, ScriptedBrain, parse_json
from loam.store.journal import Journal
from loam.store.memory import Memory


# ---------------------------------------------------------------- 素材


EXTRACT_OK = [
    {
        "summary": "对方提到最近工作压力很大",
        "questions": ["对方最近状态怎么样", "他为什么疲惫"],
        "entities": ["工作", "压力"],
        "salience": 0.6,
        "valence": -0.4,
        "stood_firm": False,
        "source_turns": [1],
    },
    {
        "summary": "角色没有顺着对方说好听的话，指出了问题所在",
        "questions": ["角色会不会讨好对方", "它顶过压力吗"],
        "entities": ["坦率"],
        "salience": 0.5,
        "valence": 0.2,
        "stood_firm": True,
        "source_turns": [2],
    },
]

APPRAISE_EMPTY = {"appraisals": [], "proposals": []}


PHASE_NAMES = {
    prompts.EXTRACT_SYSTEM: "抽事件",
    prompts.APPRAISE_SYSTEM: "判特质",
    prompts.OBSERVE_SYSTEM: "核对行为",
    prompts.DOSSIER_SYSTEM: "档案",
    prompts.NARRATE_SYSTEM: "自述",
    prompts.DRIFT_SYSTEM: "漂移比对",
}


# ---------------------------------------------------------------- 假脑子


class PhasedBrain(ScriptedBrain):
    """按"问的是哪一步"来回答的假脑子。

    比按顺序念剧本可靠得多：消化流程会跳步（没有特质时就不问行为核对，
    不到周期就不写自述），顺序剧本一跳就全错位。这里按 system 提示词
    认出是哪一步，答哪一步。

    每一项都可以是可调用对象，参数是当次的 user 提示词 —— 这样测试
    能引用"刚刚这一批抽出来的事件 id"，那些 id 在写用例时还不存在。
    """

    def __init__(self, extract=None, appraise=None, observe=None,
                 dossier=None, narrate=None, drift=None) -> None:
        super().__init__([])
        self._phases = {
            prompts.EXTRACT_SYSTEM: extract if extract is not None else EXTRACT_OK,
            prompts.APPRAISE_SYSTEM: appraise if appraise is not None else APPRAISE_EMPTY,
            prompts.OBSERVE_SYSTEM: observe if observe is not None else [],
            prompts.DOSSIER_SYSTEM: dossier if dossier is not None else [],
            prompts.NARRATE_SYSTEM: narrate if narrate is not None else "长出来的一版自述",
            prompts.DRIFT_SYSTEM: drift if drift is not None else {
                "lost": [], "drifted": [], "severity": 0.0, "note": "无"
            },
        }
        self.phase_calls = {}

    def ask(self, system: str, user: str, **kw) -> str:  # type: ignore[override]
        if system not in self._phases:
            raise BrainError("问了一个没见过的步骤 —— 提示词改了？")
        name = PHASE_NAMES[system]
        self.phase_calls[name] = self.phase_calls.get(name, 0) + 1
        self.asked.append(user)
        r = self._phases[system]
        if callable(r):
            r = r(user)
        self.usage.add(len(user) // 4, 64)
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def fresh(tmp: str, name: str = "阿萤"):
    j = Journal(os.path.join(tmp, "journal.db"))
    m = Memory(os.path.join(tmp, "memory.db"))
    return name, j, m


def feed_turns(j: Journal, character: str, n: int, session: str = "s1", start: int = 1):
    """塞 n 轮对话进日记（每轮两条：一问一答）。"""
    for i in range(start, start + n):
        j.append(character, session, i, "user", f"第{i}轮我说的话，关于工作压力")
        j.append(character, session, i, "assistant", f"第{i}轮它的回答")


def ids_in(prompt: str):
    """从提示词里把本批事件 id 抠出来。"""
    return re.findall(r"\[(ev_[0-9_]+)\]", prompt)


# ---------------------------------------------------------------- 基本链路


def test_json_parsing_tolerates_garbage():
    """模型爱裹代码块、爱加解释。全都得容忍。"""
    assert parse_json("```json\n[1,2]\n```") == [1, 2]
    assert parse_json('好的，结果是：\n{"a": 1}\n希望有帮助') == {"a": 1}
    assert parse_json('[{"x": 1}]') == [{"x": 1}]
    try:
        parse_json("完全不是 JSON")
        raise AssertionError("该抛才对")
    except ValueError:
        pass


def test_no_brain_no_cook_but_no_loss():
    """没配 key 时不许煮，但料一条都不能丢。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 12)
        d = Digester(c, j, m, Brain(api_key=""))
        before = d.pending_count()
        r = d.digest_once()
        assert r.errors, "没脑子该报错"
        assert d.pending_count() == before, "报错了料还得原样在"
        assert m.stats()["事件"] == 0
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_digest_produces_events_with_provenance():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 10)
        d = Digester(c, j, m, PhasedBrain(), batch_turns=20)

        r = d.digest_once()
        assert r.events == 2, r.as_dict()
        assert not r.errors, r.errors
        assert d.pending_count() == 0, "煮完该标记掉"

        evs = m.recent_events(limit=10)
        assert len(evs) == 2
        for e in evs:
            assert e.source_ids, "每条事件都必须指回日记"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_event_ids_are_stable_after_recompute():
    """同一批原始料重算后，事件 ID 应稳定不变。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)

        d1 = Digester(c, j, m, PhasedBrain(), batch_turns=20)
        r1 = d1.digest_once()
        assert r1.events == 2
        first_ids = sorted(e.id for e in m.recent_events(limit=10))

        m.wipe_derived()
        j.reset_digestion(c)

        d2 = Digester(c, j, m, PhasedBrain(), batch_turns=20)
        r2 = d2.digest_once()
        assert r2.events == 2
        second_ids = sorted(e.id for e in m.recent_events(limit=10))

        assert first_ids == second_ids, (first_ids, second_ids)
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_long_session_is_sharded_and_merged_before_commit():
    """长会话会分片抽取，并在入库前做分段归并。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 20)  # 40 条，强制跨多段

        def one_topic(_prompt: str):
            return [
                {
                    "summary": "对方持续在谈同一个发布准备话题",
                    "questions": ["对方最近在准备什么"],
                    "entities": ["发布"],
                    "salience": 0.55,
                    "valence": 0.1,
                    "stood_firm": False,
                    "source_turns": [1],
                }
            ]

        d = Digester(
            c,
            j,
            m,
            PhasedBrain(extract=one_topic, appraise=APPRAISE_EMPTY),
            segment_max_entries=8,
            segment_max_turn_span=4,
        )
        r = d.digest_once()

        assert int(m.get_state("extract:last_segments", "0")) >= 2
        assert int(m.get_state("extract:last_events_raw", "0")) >= 2
        assert int(m.get_state("extract:last_events_merged", "0")) == 1
        assert r.events == 1, r.as_dict()
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_stood_firm_gets_high_salience():
    """顶住压力的时刻，权重被抬到高档，但不到能绕过固化阻力那一档。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        Digester(c, j, m, PhasedBrain()).digest_once()
        firm = m.stood_firm_events()
        assert len(firm) == 1
        assert firm[0].salience >= 0.8, f"顶住压力却只有 {firm[0].salience}"
        assert firm[0].salience < BREAKTHROUGH, "顶人一次就能撬动内核，会变成滚雪球"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_events_get_woven_into_network():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        r = Digester(c, j, m, PhasedBrain()).digest_once()
        net = m.load_network()
        assert len(net) == 2, "两条事件都该进网络"
        assert r.edges >= 1, "同一批经历之间该连上"
        ids = [e.id for e in m.recent_events(limit=10)]
        assert net.weight(ids[0], ids[1]) > 0, "同批事件之间必须有连线"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_recall_crosses_causal_distance_after_digesting():
    """煮过几段经历之后，从一句新话能顺着连线走到字面上毫不相干的旧事。

    这是整个项目最要紧的那条性质：不靠字面像，靠路通。
    """
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        first = [
            {"summary": "对方说明天要做季度汇报", "questions": ["对方明天有什么安排"],
             "entities": ["汇报"], "salience": 0.6, "source_turns": [1]},
            {"summary": "对方提到上次汇报被领导中途打断", "questions": ["对方为什么怕汇报"],
             "entities": ["汇报", "领导"], "salience": 0.7, "source_turns": [2]},
        ]
        feed_turns(j, c, 4)
        d = Digester(c, j, m, PhasedBrain(extract=first))
        d.digest_once()

        second = [
            {"summary": "对方说他有点紧张", "questions": ["对方紧张的时候是什么样"],
             "entities": ["紧张", "汇报"], "salience": 0.5, "source_turns": [11]},
        ]
        feed_turns(j, c, 4, start=11)
        d.brain = PhasedBrain(extract=second)
        d.digest_once()

        net = m.load_network()
        evs = m.recent_events(limit=10)
        nervous = [e for e in evs if "紧张" in e.summary][0]
        interrupted = [e for e in evs if "打断" in e.summary][0]

        reached = {eid for eid, _ in net.spread({nervous.id: 1.0}, limit=10)}
        assert interrupted.id in reached, "从紧张出发该能走到被打断那件事"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


# ---------------------------------------------------------------- 闸门


def test_proposal_needs_two_events():
    """只有一件事支持的"发现"不算发现。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        weak = {"appraisals": [], "proposals": [
            {"text": "我倾向于直说", "event_ids": ["就这一条"], "why": "x"},
        ]}
        r = Digester(c, j, m, PhasedBrain(appraise=weak)).digest_once()
        assert r.traits_born == 0, "只有一条证据不该长出特质"
        assert len(m.load_traits()) == 0
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_proposal_with_two_events_is_born_with_provenance():
    """两条不同事件同时指向一个倾向 —— 它才允许诞生，而且带着来历。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)

        def propose(prompt: str):
            return {"appraisals": [], "proposals": [
                {"text": "我倾向于把话说明白，哪怕不好听",
                 "event_ids": ids_in(prompt)[:2], "why": "两件事都这样"},
            ]}

        r = Digester(c, j, m, PhasedBrain(appraise=propose)).digest_once()
        assert r.traits_born == 1, r.as_dict()

        traits = m.load_traits()
        assert len(traits) == 1
        t = traits[0]
        # 刚诞生：只在蓄水池里，强度还是 0 —— 新倾向不是一出生就成立的
        assert t.strength == 0.0, f"刚长出来就有 {t.strength} 的强度？"
        assert len(t._staged) == 2, "两条来历必须都留着"

        born = [h for h in m.history() if h["kind"] == "trait_born"]
        assert len(born) == 1
        assert len(born[0]["evidence"]) == 2, "诞生这件事本身也要有账"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_appraisal_without_valid_event_is_dropped():
    """指不回具体事件的判定必须被丢掉，不许兜底。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        m.save_trait(Trait(id="tr_test", text="我倾向于直说"))
        bad = {"appraisals": [
            {"trait_id": "tr_test", "signal": 1.0, "event_id": "不存在的事件"},
            {"trait_id": "查无此特质", "signal": 1.0, "event_id": "也不存在"},
        ], "proposals": []}
        r = Digester(c, j, m, PhasedBrain(appraise=bad)).digest_once()
        assert r.traits_touched == 0, "无来历的判定必须被丢"
        after = m.load_traits()[0]
        # 回弹/自主漂移会在无输入周期产生微量机械漂移（≤0.001），
        # 但蓄水池必须为空 —— 无来历的判定没有进入长期层。
        assert after.strength < 0.001 and after.pending == 0.0
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_valid_appraisal_feeds_reservoir_not_strength():
    """一次印证只进蓄水池，不会立刻改强度 —— 量变先于质变。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        m.save_trait(Trait(id="tr_x", text="我倾向于直说"))

        def confirm(prompt: str):
            return {"appraisals": [
                {"trait_id": "tr_x", "signal": 1.0, "event_id": ids_in(prompt)[0]},
            ], "proposals": []}

        r = Digester(c, j, m, PhasedBrain(appraise=confirm)).digest_once()
        assert r.traits_touched == 1, r.as_dict()
        assert r.traits_moved == 0, "一次印证不该造成质变"

        t = m.load_traits()[0]
        assert t.strength == 0.0, f"一次经历就长到 {t.strength}？太快了"
        assert t.pending > 0, "该在蓄水池里攒着"
        assert len(t._staged) == 1, "蓄水池里的来历必须跟着存下来"
        assert t.reinforced == 1
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_dossier_without_provenance_is_refused():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        brain = PhasedBrain(dossier=[
            {"key": "职业", "value": "在做一个开源项目", "event_ids": [], "confidence": 0.9},
        ])
        r = Digester(c, j, m, brain).digest_once()
        assert r.dossier_updates == 0
        assert m.dossier() == {}, "没来历的档案不许写进来"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_dossier_written_from_digest_and_old_value_kept():
    """档案卡由消化流程写入；改值时旧值不删，只标记被替代。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)

        def d1(prompt: str):
            return [{"key": "对方在做的事", "value": "在做一个开源项目",
                     "event_ids": ids_in(prompt)[:1], "confidence": 0.9}]

        d = Digester(c, j, m, PhasedBrain(dossier=d1))
        r = d.digest_once()
        assert r.dossier_updates == 1, r.as_dict()
        assert m.dossier()["对方在做的事"] == "在做一个开源项目"

        feed_turns(j, c, 4, start=70)

        def d2(prompt: str):
            return [{"key": "对方在做的事", "value": "项目已经开源了",
                     "event_ids": ids_in(prompt)[:1], "confidence": 0.9}]

        d.brain = PhasedBrain(dossier=d2)
        d.digest_once()
        assert m.dossier()["对方在做的事"] == "项目已经开源了"
        assert len(m.dossier_history("对方在做的事")) == 2, "旧值该留着"
        assert any(h["kind"] == "dossier_set" for h in m.history())
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


# ---------------------------------------------------------------- 生长


def test_repeated_confirmation_eventually_becomes_kernel():
    """一件件小事攒下去，最后自己变硬 —— 内核不是指定的，是长出来的。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_x", text="我倾向于把话说明白"))

        # 每次只有一条中等强度的印证，不含任何"重大突破"
        one_event = [{"summary": "角色又一次把话说明白了", "questions": ["它说话直吗"],
                      "entities": ["坦率"], "salience": 0.5, "source_turns": [1]}]

        def confirm(prompt: str):
            return {"appraisals": [
                {"trait_id": "tr_x", "signal": 1.0, "event_id": e} for e in ids_in(prompt)
            ], "proposals": []}

        d = Digester(c, j, m, PhasedBrain())
        trace = []
        for k in range(60):
            feed_turns(j, c, 2, start=1 + k * 10)
            d.brain = PhasedBrain(extract=one_event, appraise=confirm)
            d.digest_once()
            trace.append(round(m.load_traits()[0].strength, 4))

        t = m.load_traits()[0]
        assert t.strength > 0.85, f"印证 60 个周期还只有 {t.strength}"
        assert t.is_kernel, f"该硬了：强度 {t.strength}，来历 {len(t.evidence)} 条"

        # S 形：中段该比开头快，末段该慢下来
        early = trace[9] - trace[0]
        middle = trace[29] - trace[20]
        late = trace[59] - trace[50]
        assert middle > early, f"生长期该比萌芽期快：{early} vs {middle}"
        assert middle > late, f"接近顶点该慢下来：{middle} vs {late}"

        assert any(h["kind"] == "kernel_formed" for h in m.history(limit=500)), "内核形成没记账"
        assert m.kernel(), "kernel() 该能查出来"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_quality_change_is_logged_quantity_change_is_not():
    """质变记账，量变不记 —— 否则账本会被涨落淹掉。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_x", text="我倾向于直说"))
        one_event = [{"summary": "角色直说了一次", "questions": ["它直吗"],
                      "entities": ["坦率"], "salience": 0.3, "source_turns": [1]}]

        def confirm(prompt: str):
            return {"appraisals": [
                {"trait_id": "tr_x", "signal": 0.6, "event_id": e} for e in ids_in(prompt)
            ], "proposals": []}

        d = Digester(c, j, m, PhasedBrain())
        moved_total = 0
        for k in range(10):
            feed_turns(j, c, 2, start=1 + k * 10)
            d.brain = PhasedBrain(extract=one_event, appraise=confirm)
            moved_total += d.digest_once().traits_moved

        logged = [h for h in m.history(limit=500) if h["kind"] == "trait_moved"]
        assert len(logged) == moved_total, f"记了 {len(logged)} 笔，实际质变 {moved_total} 次"
        assert moved_total < 10, "十个周期十次质变 —— 蓄水池没起作用"
        assert moved_total > 0, "十个周期一次质变都没有 —— 太死了"
        for h in logged:
            assert h["evidence"], "每一笔都必须有依据"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_broken_model_output_keeps_raw_intact():
    """模型返回垃圾时，生料必须原样留着等下次重煮。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 6)
        before = len(j.undigested(c, limit=999))
        r = Digester(c, j, m, ScriptedBrain(["这不是JSON", "还不是JSON"])).digest_once()
        assert r.errors and r.events == 0
        assert len(j.undigested(c, limit=999)) == before, "煮失败不许吃掉料"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_small_talk_batch_is_consumed_not_stuck():
    """整批寒暄抽不出事件，也要标记掉，否则永远堵在队头。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 6)
        d = Digester(c, j, m, PhasedBrain(extract=[]))
        r = d.digest_once()
        assert r.events == 0
        assert d.pending_count() == 0, "寒暄也算看过了"
        assert m.stats()["事件"] == 0
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_ready_waits_for_batch_or_idle():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        d = Digester(c, j, m, PhasedBrain(), batch_turns=20)
        assert not d.ready(), "一条料都没有不该煮"

        feed_turns(j, c, 3)  # 6 条 < 20
        assert not d.ready(idle_seconds=9999), "没攒够又刚说完话，等着"
        assert d.ready(idle_seconds=0.0), "聊完没动静了就该收尾"

        feed_turns(j, c, 12, start=100)  # 一共 30 条
        assert d.ready(idle_seconds=9999), "攒够了就该煮"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_cycle_advances_monotonically():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        cycles = []
        for k in range(3):
            feed_turns(j, c, 3, start=1 + k * 10)
            cycles.append(Digester(c, j, m, PhasedBrain()).digest_once().cycle)
        assert cycles == [1, 2, 3], cycles
        assert m.get_state("cycle") == "3"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_skipped_phase_saves_a_call():
    """没有特质时，"核对行为"这一步该被跳过 —— 省下来的钱是白捡的。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        b1 = PhasedBrain()
        Digester(c, j, m, b1).digest_once()
        assert "核对行为" not in b1.phase_calls, "没特质还去问行为，白花钱"
        assert b1.usage.calls == 3

        m.save_trait(Trait(id="tr_a", text="我倾向于直说", strength=0.3))
        feed_turns(j, c, 4, start=60)
        b2 = PhasedBrain()
        Digester(c, j, m, b2).digest_once()
        assert b2.phase_calls.get("核对行为") == 1, "有特质就该核对行为"
        assert b2.usage.calls == 4
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


# ---------------------------------------------------------------- 自述与漂移


def test_narrative_requires_basis_and_is_written_on_schedule():
    """自述必须有来历，而且只在到点的周期才重写。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_a", text="我倾向于把话说明白", strength=0.7))
        feed_turns(j, c, 4)

        d = Digester(c, j, m, PhasedBrain())
        d.digest_once()  # cycle 1，不是 5 的倍数
        assert m.current_narrative() is None, "第 1 周期不该写自述"
        assert "自述" not in d.brain.phase_calls

        r = None
        for k in range(4):
            feed_turns(j, c, 3, start=100 + k * 10)
            d.brain = PhasedBrain(narrate="我大概是那种会把话说明白的。")
            r = d.digest_once()
        assert r.cycle == 5
        assert r.narrated, r.as_dict()
        n = m.current_narrative()
        assert n and json.loads(n["basis"]), "自述必须带来历"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_narrative_never_sees_previous_version():
    """写自述的提示词里不许出现上一版内容 —— 防复印件的复印件。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_a", text="我倾向于把话说明白", strength=0.7))
        m.add_narrative("上一版的我：一个非常独特的句子XYZ", basis=["tr_a"], cycle=0)

        brain = PhasedBrain(narrate="新的一版自述")
        Digester(c, j, m, brain)._narrate(cycle=5)
        assert "XYZ" not in "\n".join(brain.asked), "上一版泄漏进提示词了"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_identical_narrative_is_not_versioned_twice():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_a", text="我倾向于把话说明白", strength=0.7))
        d = Digester(c, j, m, PhasedBrain(narrate="同一段话"))
        assert d._narrate(cycle=5) is True
        assert d._narrate(cycle=10) is False, "一字不差就别存新版本"
        assert len(m.narrative_history()) == 1
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_low_strength_traits_are_not_narrated():
    """强度太低的倾向不该被写进"我是谁"。强度就是确定性。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_weak", text="我可能有点爱开玩笑", strength=0.05))
        brain = PhasedBrain()
        assert Digester(c, j, m, brain)._narrate(cycle=5) is False, "只有微弱倾向时不该硬写"
        assert "自述" not in brain.phase_calls
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_prompts_never_address_the_user_as_audience():
    """反思时你不在场 —— 提示词里不许出现讨好用户的措辞。"""
    banned = ["用户希望", "让用户", "请评价用户", "取悦", "讨用户", "用户喜欢"]
    for text in PHASE_NAMES:
        for b in banned:
            assert b not in text, f"提示词里出现了 {b}"


def test_audit_drift_writes_rebuilt_separately():
    """重建版是尺子，不是新的自己 —— 不许覆盖演化版。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        m.save_trait(Trait(id="tr_a", text="我倾向于把话说明白", strength=0.7))
        m.add_narrative("演化到今天的我", basis=["tr_a"], cycle=4, kind="derived")

        brain = PhasedBrain(
            narrate="从零重建出来的我",
            drift={"lost": [], "drifted": ["多了一句没根的话"], "severity": 0.3, "note": "轻微"},
        )
        verdict = Digester(c, j, m, brain).audit_drift()

        assert verdict.get("severity") == 0.3, verdict
        assert m.current_narrative("derived")["text"] == "演化到今天的我", "演化版被覆盖了"
        assert m.current_narrative("rebuilt")["text"] == "从零重建出来的我"
        assert any(h["kind"] == "drift_audit" for h in m.history())
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_rebuild_from_scratch_keeps_the_ledger():
    """从零重建：派生物可清，人格演化的账不能清。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 6)
        d = Digester(c, j, m, PhasedBrain())
        d.digest_once()
        eid = m.recent_events(limit=1)[0].id
        m.log_change(cycle=1, kind="test", reason="留个账", evidence=[eid])
        m.add_narrative("一版自述", basis=[eid], cycle=1)

        n_back = j.reset_digestion(c)
        m.wipe_derived()
        assert n_back > 0, "生料该能重新排队"
        assert m.stats()["事件"] == 0, "派生物该清掉"
        assert len(m.history()) >= 1, "账本必须留着"
        assert len(m.narrative_history()) >= 1, "自述历史必须留着"
        assert d.pending_count() == n_back, "料回到队列里了"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


# ---------------------------------------------------------------- 后台


def test_grower_runs_on_its_own():
    """后台线程自己在动 —— 没人调它也会煮。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 15)  # 30 条，够一批
        d = Digester(c, j, m, PhasedBrain())
        g = Grower(d, interval=0.05, idle_seconds=0.0, audit_every=0)
        g.start()
        assert g.alive
        deadline = time.time() + 5.0
        while time.time() < deadline and not g.reports:
            time.sleep(0.05)
        g.stop()
        assert g.reports, f"后台线程没干活：{g.last_error}"
        assert g.reports[0].events > 0
        assert not g.alive, "stop 之后该真的停了"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_grower_survives_a_broken_cycle():
    """一次煮失败不能把后台线程弄死。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 15)
        d = Digester(c, j, m, ScriptedBrain(["垃圾"] * 100))
        g = Grower(d, interval=0.05, idle_seconds=0.0, audit_every=0)
        g.start()
        time.sleep(0.5)
        alive = g.alive
        g.stop()
        assert alive, "线程死了，成长就停了"
        assert d.pending_count() > 0, "失败了料还在"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_drain_eats_everything():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 30)  # 60 条
        d = Digester(c, j, m, PhasedBrain(), batch_turns=20)
        reports = Grower(d, interval=999, audit_every=0).drain()
        assert d.pending_count() == 0, "该全煮完"
        assert len(reports) == 3, f"60 条 / 20 一批 = 3 批，实际 {len(reports)}"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_gaps_are_reconciled_before_cooking():
    """煮之前先自愈：漏掉的轮次被补上了就把缺口关掉。"""
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        for t in (1, 2, 3, 7, 8):
            j.observe_turn(c, "s1", t)
            j.append(c, "s1", t, "user", f"第{t}轮")
        assert len(j.open_gaps(c)) == 1, "该发现 4-6 缺了"

        j.append_batch(c, "s1", [
            {"turn": t, "role": "user", "content": f"补录第{t}轮"} for t in (4, 5, 6)
        ])
        d = Digester(c, j, m, PhasedBrain())
        Grower(d, interval=999, idle_seconds=0.0, audit_every=0).step()
        assert len(j.open_gaps(c)) == 0, "补上了就该关掉缺口"
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


def test_usage_is_tracked():
    tmp = tempfile.mkdtemp()
    try:
        c, j, m = fresh(tmp)
        feed_turns(j, c, 4)
        brain = PhasedBrain()
        r = Digester(c, j, m, brain).digest_once()
        assert brain.usage.calls > 0
        assert r.usage["合计"] == brain.usage.total
    finally:
        j.close(); m.close(); shutil.rmtree(tmp)


# ---------------------------------------------------------------- 跑


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
            import traceback
            print(f"  ERROR {fn.__name__}: {exc}")
            traceback.print_exc(limit=4)
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)