"""测试自性与生命力升级 (Selfhood & Vitality System Tests).

涵盖：
1. 情绪共振系统 (五行生克阻尼、序列化与心境描述)
2. 上下文心境与独处自省注入
3. 宏观性格旋钮与预设卡 (API 与常数联动)
4. 独处自省与主动惦念生成 (启发式与脑区生成)
5. 完整 HTTP 端点交互集成测试
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import loam.core.constants as C
from loam.core.persona import KNOBS_SCHEMA, PRESET_PERSONAS, map_knobs_to_constants
from loam.core.resonance import EmotionalResonanceEngine
from loam.mind.context import ContextBuilder
from loam.mind.llm import Brain
from loam.server import LoamService, ServiceConfig
from loam.store.journal import Journal
from loam.store.memory import Event, Memory


class TestVitalityResonance(unittest.TestCase):
    """测试情绪共振引擎的演化与序列化。"""

    def test_resonance_lifecycle(self) -> None:
        engine = EmotionalResonanceEngine(damping_factor=0.9, resonance_gain=0.2)

        # 初始应为心绪平和
        self.assertIn("心绪平和", engine.describe_mood())

        # 注入热情火脉冲
        engine.pulse("fire", 0.8, note="开心的对话")
        elem, val = engine.dominant_mood()
        self.assertEqual(elem, "fire")
        self.assertGreater(val, 0.5)

        mood = engine.describe_mood()
        self.assertIn("火", mood)
        self.assertIn("热情", mood)

        # 序列化与还原
        dumped = engine.to_dict()
        restored = EmotionalResonanceEngine.from_dict(dumped)
        self.assertEqual(restored.dominant_mood(), engine.dominant_mood())
        self.assertEqual(restored.describe_mood(), engine.describe_mood())

        # 相克测试：水克火
        restored.pulse("water", 0.9, note="突发惊险")
        elem2, val2 = restored.dominant_mood()
        self.assertEqual(elem2, "water")
        self.assertLess(restored.get_resonance_snapshot()["fire"], val)


class TestVitalityContextInjection(unittest.TestCase):
    """测试心境与独处自省向外部上下文的格式化注入。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="loam_test_vitality_ctx_"))
        self.memory = Memory(self.tmp / "memory.db")
        self.journal = Journal(self.tmp / "journal.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_context_renders_mood_and_daydream(self) -> None:
        builder = ContextBuilder(self.memory, journal=self.journal)

        # 1. 显式注入
        pack = builder.build(
            character="test_bot",
            query="你好呀",
            learn=False,
            mood="火气·热情开朗（能量等级：充沛，强度：+0.75）",
            proactive_thought="刚才他走开去洗澡了，我想等他回来时提醒他吹干头发。",
        )
        rendered = pack.render()
        self.assertIn("[当下心境与情绪态]", rendered)
        self.assertIn("火气·热情开朗", rendered)
        self.assertIn("[独处时的自省与惦记]", rendered)
        self.assertIn("吹干头发", rendered)

        # 2. 从持久化状态隐式加载
        engine = EmotionalResonanceEngine()
        engine.pulse("wood", 0.8)
        self.memory.set_state("resonance_state", json.dumps(engine.to_dict()))
        self.memory.set_state("current_mood", engine.describe_mood())
        self.memory.set_state("last_proactive_thought", "在窗边看着落叶发了会儿呆。")

        pack2 = builder.build(character="test_bot", query="有人在吗", learn=False)
        rendered2 = pack2.render()
        self.assertIn("[当下心境与情绪态]", rendered2)
        self.assertIn("木气·进取活跃", rendered2)
        self.assertIn("[独处时的自省与惦记]", rendered2)
        self.assertIn("在窗边看着落叶发了会儿呆", rendered2)


class TestVitalityServiceAndPersona(unittest.TestCase):
    """测试 LoamService 的性格卡片系统、共振脉冲与主动惦念机制。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="loam_test_vitality_svc_"))
        cfg = ServiceConfig(
            character="vitality_char",
            home=str(self.tmp),
            grow_interval=1.0,
            auto_start_grower=False,
        )
        self.service = LoamService(cfg)

    def tearDown(self) -> None:
        self.service.stop_grower()
        self.service.clear_constants_overrides()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_persona_preset_and_knobs(self) -> None:
        # 1. 获取默认性格
        p = self.service.get_persona()
        self.assertIn("schema", p)
        self.assertIn("presets", p)
        self.assertAlmostEqual(p["current_knobs"]["sensitivity"], 0.5)

        # 2. 应用高冷孤傲预设
        applied = self.service.apply_persona(preset="aloof")
        self.assertTrue(applied["ok"])
        self.assertEqual(applied["preset"], "aloof")
        self.assertAlmostEqual(applied["knobs"]["sensitivity"], 0.25)
        self.assertAlmostEqual(applied["knobs"]["vigilance"], 0.85)

        # 检查底层常数是否已被自动联动覆写
        self.assertAlmostEqual(C.PLASTICITY, round(0.18 + 0.37 * 0.25, 4))
        self.assertAlmostEqual(C.UNCERTAINTY_GATE, round(0.35 + 0.40 * 0.85, 4))

        # 3. 手动微调旋钮
        custom = self.service.apply_persona(knobs={"sensitivity": 0.95, "creativity": 0.90})
        self.assertTrue(custom["ok"])
        self.assertAlmostEqual(custom["knobs"]["sensitivity"], 0.95)
        self.assertAlmostEqual(C.PLASTICITY, round(0.18 + 0.37 * 0.95, 4))

        # 4. 重置为默认平衡态
        reset = self.service.reset_persona()
        self.assertTrue(reset["ok"])
        self.assertAlmostEqual(reset["knobs"]["sensitivity"], 0.5)

    def test_proactive_thought_generation_and_storage(self) -> None:
        # 初始无惦记
        init_t = self.service.proactive_thought()
        self.assertIsNone(init_t["thought"])

        # 添加一条事件，测试离线启发式惦念生成
        now = time.time()
        ev = Event(
            id="ev_001",
            summary="和用户聊到了去学习量子力学的事情",
            source_ids=[1, 2],
            session="s1",
            salience=0.8,
            valence=0.6,
            questions=["量子纠缠到底是怎么回事？"],
            entities=["量子力学"],
            happened_at=now,
        )
        self.service.memory.add_event(ev)

        # 触发自省
        res = self.service.generate_proactive_thought(force=True)
        self.assertTrue(res["ok"])
        self.assertIsNotNone(res["thought"])
        self.assertIn("量子纠缠", res["thought"])

        # 再次获取
        cur = self.service.proactive_thought()
        self.assertEqual(cur["thought"], res["thought"])

    def test_digest_pulses_resonance_and_builds_rich_context(self) -> None:
        # 写入生料并消化
        self.service.ingest({
            "session": "s_res",
            "turns": [
                {"turn": 1, "role": "user", "content": "今天真是太开心了，拿到了全校一等奖！"},
                {"turn": 2, "role": "assistant", "content": "恭喜你！这真的是非常值得庆祝的荣誉！"},
            ],
        })

        # digest_once (使用 MockBrain)
        report = self.service.digest_once()
        self.assertIn("resonance", report)
        self.assertIn("mood", report)

        # 脉冲后检查 context
        ctx = self.service.build_context("今天真开心")
        self.assertIn("resonance", ctx)
        self.assertIn("mood", ctx)
        self.assertIn("[当下心境与情绪态]", ctx["text"])

    def test_grower_idle_daydream_hook(self) -> None:
        self.assertIsNotNone(self.service.grower.on_daydream)
        # 触发 3 次 _maybe_daydream，模拟连续空闲步数
        self.service.grower._maybe_daydream()
        self.service.grower._maybe_daydream()
        self.service.grower._maybe_daydream()
        thought = self.service.proactive_thought()
        self.assertIsNotNone(thought["thought"])


class TestVitalityHttpApi(unittest.TestCase):
    """测试新增加的自性与生命力 HTTP REST API 端点。"""

    def setUp(self) -> None:
        from loam.server import build_server
        import urllib.request
        self.tmp = Path(tempfile.mkdtemp(prefix="loam_test_vitality_api_"))
        cfg = ServiceConfig(
            character="api_vitality_bot",
            home=str(self.tmp),
            grow_interval=1.0,
            auto_start_grower=False,
        )
        self.service = LoamService(cfg)
        self.server = build_server(self.service, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.th = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.th.start()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.service.close()
        self.service.clear_constants_overrides()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get(self, path: str) -> dict:
        import urllib.request
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())

    def _post(self, path: str, payload: dict) -> dict:
        import urllib.request
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())

    def test_persona_endpoints(self) -> None:
        # GET /persona
        p = self._get("/persona")
        self.assertIn("schema", p)
        self.assertIn("presets", p)
        self.assertIn("aloof", p["presets"])

        # POST /persona/apply preset
        res = self._post("/persona/apply", {"preset": "gentle"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["preset"], "gentle")
        self.assertAlmostEqual(res["knobs"]["sensitivity"], 0.75)

        # POST /persona/apply custom knobs
        res2 = self._post("/persona/apply", {"knobs": {"sensitivity": 0.88}})
        self.assertTrue(res2["ok"])
        self.assertAlmostEqual(res2["knobs"]["sensitivity"], 0.88)

        # POST /persona/reset
        res3 = self._post("/persona/reset", {})
        self.assertTrue(res3["ok"])
        self.assertAlmostEqual(res3["knobs"]["sensitivity"], 0.5)

    def test_resonance_endpoints(self) -> None:
        # GET /resonance
        r = self._get("/resonance")
        self.assertIn("dominant_element", r)
        self.assertIn("elements", r)

        # POST /resonance/pulse
        pulse_res = self._post("/resonance/pulse", {"element": "fire", "intensity": 0.75, "note": "开心的赞美"})
        self.assertTrue(pulse_res["ok"])
        self.assertEqual(pulse_res["element"], "fire")
        self.assertGreater(pulse_res["resonance"]["fire"], 0.5)
        self.assertIn("火", pulse_res["mood"])

    def test_proactive_endpoints(self) -> None:
        # POST /proactive
        p_res = self._post("/proactive", {"force": True})
        self.assertTrue(p_res["ok"])
        self.assertIsNotNone(p_res["thought"])

        # GET /proactive
        cur = self._get("/proactive")
        self.assertEqual(cur["thought"], p_res["thought"])


if __name__ == "__main__":
    unittest.main()
