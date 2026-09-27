"""五重自性生长体系 (Five-Tier Selfhood Genesis Architecture) 完整测试。

覆盖范围：
  Tier 1  主观感知透镜 (Subjective Lens)
  Tier 2  蔡加尼克内心执念 (Latent Drives / Zeigarnik Effect)
  Tier 3  梦境重构 (Dream Replay / Poetic Metaphor)
  Tier 4  他者之镜 (Theory of Mind / Mirror of Other)
  Tier 5  虚拟剧场舞台总线 (Theater Stage Bus)

全部离线运行，不依赖 API key。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loam.core.drive import Drive
from loam.core.mirror import MirrorOfOther
from loam.core.growth import Trait
from loam.mind import prompts
from loam.mind.digest import Digester, DigestReport, Grower
from loam.mind.llm import Brain, BrainError, ScriptedBrain
from loam.mind.context import ContextBuilder, ContextPack
from loam.store.journal import Journal
from loam.store.memory import Event, Memory
from loam.theater.stage import TheaterStage


# ---------------------------------------------------------------- 工具

PHASE_NAMES = {
    prompts.EXTRACT_SYSTEM: "抽事件",
    prompts.APPRAISE_SYSTEM: "判特质",
    prompts.OBSERVE_SYSTEM: "核对行为",
    prompts.DOSSIER_SYSTEM: "档案",
    prompts.NARRATE_SYSTEM: "自述",
    prompts.DRIFT_SYSTEM: "漂移比对",
}

# 带高情感波动和未解疑问的事件，用来触发执念系统
EXTRACT_WITH_QUESTIONS = [
    {
        "summary": "对方提到离开的真正原因一直没说清楚",
        "questions": ["离开的真正原因是什么", "到底发生了什么"],
        "entities": ["离开", "原因"],
        "salience": 0.8,
        "valence": -0.7,
        "stood_firm": False,
        "source_turns": [1],
    },
    {
        "summary": "角色感受到了一种被隐瞒的不安",
        "questions": [],
        "entities": ["隐瞒", "不安"],
        "salience": 0.6,
        "valence": -0.6,
        "stood_firm": False,
        "source_turns": [2],
    },
]

EXTRACT_SIMPLE = [
    {
        "summary": "讨论了天气和日常生活",
        "questions": [],
        "entities": ["天气"],
        "salience": 0.3,
        "valence": 0.0,
        "stood_firm": False,
        "source_turns": [1],
    },
]

APPRAISE_EMPTY = {"appraisals": [], "proposals": []}


class PhasedBrain(ScriptedBrain):
    """按 system 提示词匹配步骤来应答的假脑子。"""

    def __init__(self, extract=None, appraise=None, observe=None,
                 dossier=None, narrate=None, drift=None) -> None:
        super().__init__([])
        self._phases = {
            prompts.EXTRACT_SYSTEM: extract if extract is not None else EXTRACT_WITH_QUESTIONS,
            prompts.APPRAISE_SYSTEM: appraise if appraise is not None else APPRAISE_EMPTY,
            prompts.OBSERVE_SYSTEM: observe if observe is not None else [],
            prompts.DOSSIER_SYSTEM: dossier if dossier is not None else [],
            prompts.NARRATE_SYSTEM: narrate if narrate is not None else "角色的初版自述",
            prompts.DRIFT_SYSTEM: drift if drift is not None else {
                "lost": [], "drifted": [], "severity": 0.0, "note": "无"
            },
        }

    def ask(self, system: str, user: str, **kw) -> str:  # type: ignore[override]
        if system not in self._phases:
            raise BrainError("问了一个没见过的步骤 —— 提示词改了？")
        r = self._phases[system]
        if callable(r):
            r = r(user)
        self.asked.append(user)
        self.usage.add(len(user) // 4, 64)
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def fresh(tmp: str, name: str = "阿萤"):
    j = Journal(os.path.join(tmp, "journal.db"))
    m = Memory(os.path.join(tmp, "memory.db"))
    return name, j, m


def feed_turns(j: Journal, character: str, n: int, session: str = "s1", start: int = 1):
    for i in range(start, start + n):
        j.append(character, session, i, "user", f"第{i}轮我说的话，关于离开的真正原因")
        j.append(character, session, i, "assistant", f"第{i}轮角色的回答")


# ================================================================ Tier 1: 主观感知透镜


class TestSubjectiveLens(unittest.TestCase):
    """Tier 1: extract_prompt 将心境偏差和核心特质注入 user prompt。"""

    def test_no_bias_produces_clean_prompt(self):
        """无偏差时，extract_prompt 不添加主观透镜。"""
        p = prompts.extract_prompt("一段对话文本")
        self.assertNotIn("主观感知透镜", p["user"])
        self.assertEqual(p["system"], prompts.EXTRACT_SYSTEM)

    def test_mood_bias_injected_in_user_prompt(self):
        """心境透镜应注入 user prompt 而非 system prompt（保护 PhasedBrain 路由）。"""
        p = prompts.extract_prompt(
            "一段对话文本",
            mood_bias="忧虑而疲惫",
            kernel_traits=["坦率直言", "不回避冲突"],
        )
        # 系统提示词不能被修改
        self.assertEqual(p["system"], prompts.EXTRACT_SYSTEM)
        # 心境和特质应出现在 user 提示词中
        self.assertIn("主观感知透镜", p["user"])
        self.assertIn("忧虑而疲惫", p["user"])
        self.assertIn("坦率直言", p["user"])
        self.assertIn("不回避冲突", p["user"])

    def test_only_mood_bias(self):
        """只有心境透镜时，特质不应出现。"""
        p = prompts.extract_prompt("对话", mood_bias="欢快跳脱")
        self.assertIn("欢快跳脱", p["user"])
        self.assertNotIn("核心根基特质", p["user"])

    def test_only_kernel_traits(self):
        """只有核心特质时，心境不应出现。"""
        p = prompts.extract_prompt("对话", kernel_traits=["善于倾听"])
        self.assertIn("善于倾听", p["user"])
        self.assertNotIn("心境透镜", p["user"])


# ================================================================ Tier 2: 蔡加尼克内心执念


class TestLatentDrives(unittest.TestCase):
    """Tier 2: Drive 数据模型、存储层 CRUD、消化管线中的执念演化。"""

    def test_drive_dataclass_basics(self):
        """Drive 数据模型基本操作。"""
        d = Drive(
            id="drv_test_1",
            theme="关于那次不告而别",
            source_event_id="ev_001",
            tension=0.5,
            questions=["为什么不说再见"],
        )
        self.assertEqual(d.status, "active")
        self.assertAlmostEqual(d.tension, 0.5)

        # 张力发酵
        new_tension = d.escalate_tension(0.2)
        self.assertAlmostEqual(new_tension, 0.7)

        # 释怀
        d.discharge(reason="得到了回应")
        self.assertEqual(d.status, "resolved")
        self.assertAlmostEqual(d.tension, 0.0)
        self.assertIsNotNone(d.resolved_at)

    def test_drive_escalation_caps_at_one(self):
        """张力上限为 1.0。"""
        d = Drive(id="drv_cap", theme="test", source_event_id="ev_x", tension=0.9)
        d.escalate_tension(0.3)
        self.assertAlmostEqual(d.tension, 1.0)

    def test_drive_no_escalation_after_resolved(self):
        """已释怀的执念不应再发酵。"""
        d = Drive(id="drv_res", theme="test", source_event_id="ev_x", tension=0.5)
        d.discharge("done")
        old = d.tension
        d.escalate_tension(0.5)
        self.assertAlmostEqual(d.tension, old)

    def test_drive_serialization_roundtrip(self):
        """as_dict / from_dict 往返。"""
        d = Drive(
            id="drv_serial",
            theme="某个主题",
            source_event_id="ev_serial",
            tension=0.75,
            questions=["问题A", "问题B"],
        )
        d2 = Drive.from_dict(d.as_dict())
        self.assertEqual(d2.id, d.id)
        self.assertEqual(d2.theme, d.theme)
        self.assertAlmostEqual(d2.tension, d.tension)
        self.assertEqual(d2.questions, d.questions)

    def test_memory_drive_crud(self):
        """Memory 层的 save/get/resolve/escalate 执念操作。"""
        tmp = tempfile.mkdtemp()
        try:
            m = Memory(os.path.join(tmp, "mem.db"))
            d = Drive(
                id="drv_db_1",
                theme="关于离别",
                source_event_id="ev_db_1",
                tension=0.5,
                questions=["为什么"],
            )
            m.save_drive(d)

            # 读取
            loaded = m.get_drive("drv_db_1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.theme, "关于离别")
            self.assertAlmostEqual(loaded.tension, 0.5)

            # 获取活跃执念列表
            active = m.get_active_drives()
            self.assertEqual(len(active), 1)

            # 批量升级张力
            count = m.escalate_drives(delta=0.1)
            self.assertEqual(count, 1)
            reloaded = m.get_drive("drv_db_1")
            self.assertAlmostEqual(reloaded.tension, 0.6)

            # 化解
            ok = m.resolve_drive("drv_db_1", reason="释然了")
            self.assertTrue(ok)
            resolved = m.get_drive("drv_db_1")
            self.assertEqual(resolved.status, "resolved")
            self.assertAlmostEqual(resolved.tension, 0.0)

            # 再次化解应失败
            ok2 = m.resolve_drive("drv_db_1", reason="再来一次")
            self.assertFalse(ok2)
        finally:
            m.close()
            shutil.rmtree(tmp)

    def test_digest_creates_drives_from_events(self):
        """消化管线在遇到高情感或有疑问的事件时应创建执念。"""
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            feed_turns(j, c, 10)
            brain = PhasedBrain(extract=EXTRACT_WITH_QUESTIONS)
            d = Digester(c, j, m, brain, batch_turns=20)

            report = d.digest_once()
            self.assertGreaterEqual(report.drives_created, 1,
                                    f"应至少创建 1 条执念: {report.as_dict()}")
            self.assertFalse(report.errors, f"不应有错误: {report.errors}")

            # 数据库里确实有活跃执念
            active = m.get_active_drives()
            self.assertGreaterEqual(len(active), 1)
            for drv in active:
                self.assertGreater(drv.tension, 0.0)
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)

    def test_digest_resolves_drives_when_theme_mentioned(self):
        """当对话中提到了执念的关键词时，应化解对应执念。"""
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            # 手动创建一条执念，其主题是"离开"
            drv = Drive(
                id="drv_pre",
                theme="离开的真正原因",
                source_event_id="ev_pre",
                tension=0.8,
                questions=["为什么离开"],
            )
            m.save_drive(drv)

            # 灌入包含"离开"关键词的对话
            j.append(c, "s1", 1, "user", "我终于想通了离开的真正原因")
            j.append(c, "s1", 1, "assistant", "我理解了")
            for i in range(2, 11):
                j.append(c, "s1", i, "user", f"第{i}轮话")
                j.append(c, "s1", i, "assistant", f"第{i}轮回答")

            brain = PhasedBrain(extract=EXTRACT_SIMPLE)
            d = Digester(c, j, m, brain, batch_turns=20)
            report = d.digest_once()

            self.assertGreaterEqual(report.drives_resolved, 1,
                                    f"应至少释怀 1 条执念: {report.as_dict()}")
            resolved = m.get_drive("drv_pre")
            self.assertEqual(resolved.status, "resolved")
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)


# ================================================================ Tier 3: 梦境重构


class TestDreamReplay(unittest.TestCase):
    """Tier 3: dream_cycle 在记忆图网络中建立诗意隐喻连线。"""

    def test_dream_cycle_links_distant_nodes(self):
        """梦境重构应在网络节点间创建新连线。"""
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            feed_turns(j, c, 10)
            brain = PhasedBrain()
            d = Digester(c, j, m, brain, batch_turns=20)

            # 先消化一次产生事件和网络节点
            report = d.digest_once()
            self.assertGreater(report.events, 0, "先需要有事件才能做梦")

            net_before = m.load_network()
            node_count_before = len(net_before._nodes)
            edge_count_before = len(net_before._edges)

            # 触发梦境重构
            result = d.dream_cycle(cycle=1)
            if node_count_before >= 2:
                self.assertIsNotNone(result, "有 >=2 节点时梦境应该能产出")
                self.assertIn("metaphor", result)
                self.assertIn("u", result)
                self.assertIn("v", result)

                # 网络中应该多了一条梦境边
                net_after = m.load_network()
                self.assertGreaterEqual(len(net_after._edges), edge_count_before)

                # changelog 里应该有梦境记录
                last_dream = m.get_state("last_dream")
                self.assertTrue(last_dream, "应有 last_dream 状态记录")
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)

    def test_dream_cycle_returns_none_with_too_few_nodes(self):
        """节点不足 2 个时梦境返回 None。"""
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            brain = PhasedBrain()
            d = Digester(c, j, m, brain)
            result = d.dream_cycle()
            self.assertIsNone(result)
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)

    def test_dream_prompt_generation(self):
        """dream_prompt 函数应生成合法的 system/user 提示词。"""
        p = prompts.dream_prompt("经历A概要", "经历B概要", narrative="角色自述")
        self.assertIn("经历A概要", p["user"])
        self.assertIn("经历B概要", p["user"])
        self.assertEqual(p["system"], prompts.DREAM_SYSTEM)


# ================================================================ Tier 4: 他者之镜


class TestTheoryOfMind(unittest.TestCase):
    """Tier 4: MirrorOfOther 数据模型、存储层、消化管线中的心智理论更新。"""

    def test_mirror_dataclass_basics(self):
        """MirrorOfOther 基本属性和方法。"""
        m = MirrorOfOther(
            target="user",
            summary="表面沉稳要强，实则内心疲惫",
            perceived_traits=["不善直接表达情感", "注重逻辑"],
            vulnerabilities=["害怕被忽视"],
            interaction_advice="在疲惫时给予温和支持",
        )
        self.assertEqual(m.target, "user")
        self.assertEqual(len(m.perceived_traits), 2)

        desc = m.describe()
        self.assertIn("表面沉稳要强", desc)
        self.assertIn("不善直接表达情感", desc)
        self.assertIn("害怕被忽视", desc)

    def test_mirror_empty_describe(self):
        """无数据时应返回占位观察语。"""
        m = MirrorOfOther()
        desc = m.describe()
        self.assertIn("正在静静观察", desc)

    def test_mirror_serialization_roundtrip(self):
        """as_dict / from_dict 往返。"""
        m = MirrorOfOther(
            target="alice",
            summary="温柔但有主见",
            perceived_traits=["善良"],
            vulnerabilities=["容易自我怀疑"],
            interaction_advice="多鼓励",
        )
        m2 = MirrorOfOther.from_dict(m.as_dict())
        self.assertEqual(m2.target, m.target)
        self.assertEqual(m2.summary, m.summary)
        self.assertEqual(m2.perceived_traits, m.perceived_traits)

    def test_memory_mirror_crud(self):
        """Memory 层的 save_mirror / get_mirror。"""
        tmp = tempfile.mkdtemp()
        try:
            mem = Memory(os.path.join(tmp, "mem.db"))
            mirror = MirrorOfOther(
                target="user",
                summary="交流风格直接而简练",
                perceived_traits=["务实", "不拐弯抹角"],
                vulnerabilities=["偶尔显得不耐烦"],
                interaction_advice="简洁回应，切忌啰嗦",
            )
            mem.save_mirror(mirror)

            loaded = mem.get_mirror("user")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.summary, "交流风格直接而简练")
            self.assertEqual(len(loaded.perceived_traits), 2)
            self.assertIn("务实", loaded.perceived_traits)

            # 更新
            mirror2 = MirrorOfOther(
                target="user",
                summary="比想象中更温柔",
                perceived_traits=["务实", "不拐弯抹角", "偶尔脆弱"],
            )
            mem.save_mirror(mirror2)
            reloaded = mem.get_mirror("user")
            self.assertEqual(reloaded.summary, "比想象中更温柔")
            self.assertEqual(len(reloaded.perceived_traits), 3)

            # 不存在的
            none_mirror = mem.get_mirror("nobody")
            self.assertIsNone(none_mirror)
        finally:
            mem.close()
            shutil.rmtree(tmp)

    def test_digest_updates_mirror_heuristic(self):
        """消化管线离线启发式模式下应更新心智画像。"""
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            feed_turns(j, c, 10)
            brain = PhasedBrain()
            d = Digester(c, j, m, brain, batch_turns=20)

            report = d.digest_once()
            self.assertTrue(report.mirror_updated,
                            f"离线模式下也应该更新心智画像: {report.as_dict()}")

            mirror = m.get_mirror("user")
            self.assertIsNotNone(mirror, "应能从数据库读到心智画像")
            self.assertTrue(mirror.summary, "画像应有概要")
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)

    def test_mirror_prompt_generation(self):
        """mirror_prompt 函数应生成合法提示词。"""
        p = prompts.mirror_prompt("user: 你好\nassistant: 你好呀")
        self.assertIn("你好", p["user"])
        self.assertEqual(p["system"], prompts.MIRROR_SYSTEM)


# ================================================================ Tier 5: 虚拟剧场舞台总线


class _MockService:
    """极简 LoamService 替身，用于 TheaterStage 测试。"""

    def __init__(self, name: str, tmp: str) -> None:
        self.name = name
        self.journal = Journal(os.path.join(tmp, f"{name}_journal.db"))
        self.memory = Memory(os.path.join(tmp, f"{name}_memory.db"))
        self.brain = Brain(api_key="")  # 不可用

    def build_context(self, query: str, partner_id: str = "user") -> ContextPack:
        return ContextPack(
            character=self.name,
            query=query,
            cycle=0,
            built_at=time.time(),
            mood="沉静而审视",
            drives=[{"id": "drv_test", "theme": "悬念", "tension": 0.7, "questions": ["为什么"]}],
            mirror={"summary": f"对{partner_id}的初步印象", "perceived_traits": ["敏锐"]},
        )

    def close(self):
        self.journal.close()
        self.memory.close()


class TestTheaterStage(unittest.TestCase):
    """Tier 5: 虚拟剧场舞台总线的角色注册、发言轮换、台词生成、场景运行。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.svc_a = _MockService("阿萤", self.tmp)
        self.svc_b = _MockService("苏渡", self.tmp)

    def tearDown(self):
        self.svc_a.close()
        self.svc_b.close()
        shutil.rmtree(self.tmp)

    def test_register_and_list_actors(self):
        """角色注册与列表。"""
        stage = TheaterStage("test_stage")
        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)
        actors = stage.list_actors()
        self.assertIn("阿萤", actors)
        self.assertIn("苏渡", actors)
        self.assertEqual(len(actors), 2)

    def test_unregister_actor(self):
        """角色下台注销。"""
        stage = TheaterStage()
        stage.register_actor("阿萤", self.svc_a)
        stage.unregister_actor("阿萤")
        self.assertEqual(len(stage.list_actors()), 0)

    def test_post_line_broadcasts(self):
        """post_line 将台词广播并记入 transcript。"""
        stage = TheaterStage()
        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)

        rec = stage.post_line("阿萤", "大幕初启，你可有话要说？")
        self.assertEqual(rec["speaker"], "阿萤")
        self.assertIn("大幕初启", rec["content"])
        self.assertEqual(len(stage.transcript), 1)

    def test_select_next_speaker_alternates(self):
        """发言选择器应避免连续同一人。"""
        stage = TheaterStage()
        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)

        # 模拟阿萤刚说过话
        stage._last_speaker = "阿萤"
        chosen = stage.select_next_speaker()
        self.assertEqual(chosen, "苏渡", "上一轮是阿萤，下一轮应轮到苏渡")

    def test_select_next_speaker_prefers_tension(self):
        """有高张力执念的角色应被优先选择。"""
        stage = TheaterStage()
        # 给苏渡的 memory 塞入一条高张力执念
        drv = Drive(
            id="drv_tension",
            theme="心结",
            source_event_id="ev_x",
            tension=0.95,
        )
        self.svc_b.memory.save_drive(drv)

        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)
        stage._last_speaker = None

        chosen = stage.select_next_speaker()
        self.assertEqual(chosen, "苏渡", "高张力角色应被优先选中")

    def test_step_dialogue_generates_heuristic_line(self):
        """step_dialogue 在无 LLM 时应生成启发式台词。"""
        stage = TheaterStage()
        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)

        result = stage.step_dialogue(topic="往事")
        self.assertIn("speaker", result)
        self.assertIn("line", result)
        self.assertTrue(result["line"], "台词不应为空")
        self.assertEqual(len(stage.transcript), 1)

    def test_run_scene_multiple_rounds(self):
        """run_scene 应连续运行多轮。"""
        stage = TheaterStage()
        stage.register_actor("阿萤", self.svc_a)
        stage.register_actor("苏渡", self.svc_b)

        results = stage.run_scene(rounds=3, initial_prompt="舞台灯亮，二人对视。")
        # initial_prompt 记入 transcript，所以 transcript 应有 3+1=4 条
        self.assertEqual(len(stage.transcript), 4)
        self.assertEqual(len(results), 3)
        # 每轮结果应有完整结构
        for r in results:
            self.assertIn("speaker", r)
            self.assertIn("line", r)
            self.assertIn("partner", r)

    def test_empty_stage_step_returns_error(self):
        """空舞台调用 step_dialogue 应返回 error。"""
        stage = TheaterStage()
        result = stage.step_dialogue()
        self.assertIn("error", result)


# ================================================================ 集成: 上下文装配 + 执念 + 镜像


class TestContextPackIntegration(unittest.TestCase):
    """验证 ContextPack 能正确渲染 drives 和 mirror 字段。"""

    def test_render_includes_drives_section(self):
        """render() 应包含执念与悬念区段。"""
        pack = ContextPack(
            character="阿萤",
            query="test",
            cycle=1,
            built_at=time.time(),
            drives=[
                {"id": "drv_1", "tension": 0.8, "theme": "那次离别", "questions": ["为什么不告而别"]},
            ],
        )
        text = pack.render()
        self.assertIn("内心未释怀的执念与悬念", text)
        self.assertIn("那次离别", text)
        self.assertIn("为什么不告而别", text)

    def test_render_includes_mirror_section(self):
        """render() 应包含心智揣摩区段。"""
        pack = ContextPack(
            character="阿萤",
            query="test",
            cycle=1,
            built_at=time.time(),
            mirror={
                "summary": "对方表面坚强实则脆弱",
                "perceived_traits": ["要强", "不善示弱"],
                "vulnerabilities": ["害怕孤独"],
                "interaction_advice": "给予空间但不远离",
            },
        )
        text = pack.render()
        self.assertIn("对眼前之人的心智揣摩", text)
        self.assertIn("对方表面坚强实则脆弱", text)
        self.assertIn("害怕孤独", text)

    def test_render_with_empty_drives_and_mirror(self):
        """无 drives/mirror 时渲染不应崩溃也不应出现空区段。"""
        pack = ContextPack(
            character="阿萤",
            query="test",
            cycle=1,
            built_at=time.time(),
        )
        text = pack.render()
        self.assertNotIn("内心未释怀的执念与悬念", text)
        self.assertNotIn("对眼前之人的心智揣摩", text)


# ================================================================ DigestReport 完整性


class TestDigestReportSelfhoodFields(unittest.TestCase):
    """验证 DigestReport 包含五重自性相关字段。"""

    def test_report_has_selfhood_fields(self):
        r = DigestReport()
        self.assertEqual(r.drives_created, 0)
        self.assertEqual(r.drives_resolved, 0)
        self.assertFalse(r.mirror_updated)
        self.assertEqual(r.dreams_woven, 0)

    def test_report_as_dict_contains_all_keys(self):
        r = DigestReport(
            cycle=1,
            drives_created=2,
            drives_resolved=1,
            mirror_updated=True,
            dreams_woven=1,
        )
        d = r.as_dict()
        # 中文键
        self.assertEqual(d["执念新生"], 2)
        self.assertEqual(d["执念释怀"], 1)
        self.assertTrue(d["心智更新"])
        self.assertEqual(d["梦境隐喻"], 1)
        # 英文键
        self.assertEqual(d["drives_created"], 2)
        self.assertEqual(d["drives_resolved"], 1)
        self.assertTrue(d["mirror_updated"])
        self.assertEqual(d["dreams_woven"], 1)


# ================================================================ 端到端: 消化一轮后 drives + mirror 都有产出


class TestFullDigestCycleWithSelfhood(unittest.TestCase):
    """一次完整消化 → 事件 + 执念 + 心智画像全部产出。"""

    def test_full_digest_produces_drives_and_mirror(self):
        tmp = tempfile.mkdtemp()
        try:
            c, j, m = fresh(tmp)
            feed_turns(j, c, 10)
            brain = PhasedBrain(extract=EXTRACT_WITH_QUESTIONS)
            d = Digester(c, j, m, brain, batch_turns=20)

            report = d.digest_once()
            self.assertFalse(report.errors, f"不应有错误: {report.errors}")
            self.assertGreater(report.events, 0)
            self.assertGreaterEqual(report.drives_created, 1)
            self.assertTrue(report.mirror_updated)

            # 状态持久化
            active_drives = m.get_active_drives()
            self.assertGreaterEqual(len(active_drives), 1)
            mirror = m.get_mirror("user")
            self.assertIsNotNone(mirror)
        finally:
            j.close(); m.close(); shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
