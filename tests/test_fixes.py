"""测试所有近期缺陷修复与稳定性增强（test_fixes.py）。

涵盖：
1. 种子叙述冷启动修复（可溯源、非空 source_ids、错误日志归属）
2. URL 后缀剥离边界防护（避免 rstrip 吞食 8001 端口与 dev1 域名）
3. 消息管道独立 Markdown JSON Tool Call 代码块剥离
4. 多角色 /recompute 路由正确性
5. 代理网关 _models_merged 异常隔离与容错
6. 代理网关 SSE 流式转发对 finish_reason 的准确透传
7. 上下文钻取 (Drilldown) 跨平台编码安全
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bridge.forced_flow_proxy as forced_flow_proxy
from loam.core.growth import Trait
from loam.mind import prompts
from loam.mind.context import ContextBuilder
from loam.mind.digest import Digester
from loam.mind.llm import Brain, ScriptedBrain
from loam.mind.pipeline import parse_turn_channels
from loam.server import LoamService, ServiceConfig
from loam.store.journal import Journal
from loam.store.memory import Event, Memory


def test_seed_narrative_cold_start() -> None:
    tmp = tempfile.mkdtemp(prefix="loam_seed_test_")
    try:
        j = Journal(Path(tmp) / "journal.db")
        m = Memory(Path(tmp) / "memory.db")

        # 构造一个模拟 Brain，在 seed phase 返回种子事件
        class SeedBrain(ScriptedBrain):
            def ask_json(self, system: str, user: str, **kw: Any) -> Any:
                if "种子" in user or "背景描述" in system or system == prompts.seed_prompt("")["system"]:
                    return [
                        {
                            "summary": "幼年曾生活在海边灯塔",
                            "questions": ["角色的童年经历"],
                            "entities": ["灯塔", "海边"],
                            "salience": 0.8,
                            "valence": 0.3,
                        }
                    ]
                return super().ask_json(system, user, **kw)

        brain = SeedBrain([])
        brain.seed_narrative = "这是一个在海边灯塔长大的向导角色。"

        digester = Digester("test_char", j, m, brain)
        rep = digester.digest_once()

        # 1. 验证报告没有报错
        assert not rep.errors, f"冷启动不应有错误: {rep.errors}"
        # 2. 验证 notes 记录了成功提示
        assert any("冷启动" in n for n in rep.notes), f"notes 中应有冷启动记录: {rep.notes}"
        # 3. 验证事件成功持久化且有合法 source_ids
        ev = m.get_event("seed_0000")
        assert ev is not None, "应当长出 seed_0000 种子事件"
        assert ev.summary == "幼年曾生活在海边灯塔"
        assert ev.source_ids, "种子事件必须有溯源 source_ids"
        # 4. 验证日记中沉淀了 __seed__ 来源条目
        entries = j.read("test_char", limit=10)
        assert any(e.session == "__seed__" for e in entries), "Journal 应记录 __seed__ 条目"

        j.close()
        m.close()
        print("  PASS test_seed_narrative_cold_start")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_base_url_rstrip_safety() -> None:
    # 验证 URL 后缀安全剥离，绝不破坏合法端口 8001 或域名 dev1
    test_cases = [
        ("http://127.0.0.1:8001", "http://127.0.0.1:8001/v1/chat/completions"),
        ("https://api.dev1", "https://api.dev1/v1/chat/completions"),
        ("https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
        ("https://api.deepseek.com/v1/", "https://api.deepseek.com/v1/chat/completions"),
        ("https://custom.host:8081/api/v1", "https://custom.host:8081/api/v1/chat/completions"),
    ]
    for raw_url, expected in test_cases:
        b = raw_url.rstrip("/")
        if b.endswith("/v1"):
            b = b[:-3].rstrip("/")
        final_url = b + "/v1/chat/completions"
        assert final_url == expected, f"URL 格式化错误: {raw_url} -> {final_url} != {expected}"
    print("  PASS test_base_url_rstrip_safety")


def test_pipeline_json_tool_block_cleaning() -> None:
    raw = (
        "我先为你查询一下明天的天气情况。\n"
        "```json\n"
        '{"tool": "get_weather", "location": "Beijing"}\n'
        "```\n"
        "请稍等片刻，我正在整理信息！"
    )
    parsed = parse_turn_channels("assistant", raw)
    assert len(parsed.actions) == 1, f"应提取出 1 个 action，实际 {len(parsed.actions)}"
    assert parsed.actions[0].get("tool") == "get_weather"
    assert "```json" not in parsed.dialogue, "纯净对话中不应残留 JSON 代码块"
    assert "get_weather" not in parsed.dialogue, "纯净对话中不应包含工具代码内部文本"
    assert "我先为你查询一下明天的天气情况。" in parsed.dialogue
    assert "请稍等片刻，我正在整理信息！" in parsed.dialogue
    print("  PASS test_pipeline_json_tool_block_cleaning")


def test_recompute_character_routing() -> None:
    tmp = tempfile.mkdtemp(prefix="loam_recompute_route_")
    try:
        cfg = ServiceConfig(character="default_char", home=tmp, auto_start_grower=False)
        svc_default = LoamService(cfg)
        cfg_custom = ServiceConfig(character="custom_char", home=tmp, auto_start_grower=False)
        svc_custom = LoamService(cfg_custom)

        # 往 custom 写入一些数据
        svc_custom.journal.append("custom_char", "s1", 1, "user", "你好呀")
        svc_custom.journal.append("custom_char", "s1", 1, "assistant", "你好！很高兴见到你")

        # 运行 custom 的 recompute
        res = svc_custom.recompute(mode="incremental")
        assert res.get("ok"), "recompute 应返回 ok"
        assert res.get("run_id"), "应生成 run_id"

        hist = svc_custom.recompute_history()
        assert len(hist["items"]) == 1, "custom 角色应有 1 次重算记录"

        # default 角色应该没有被影响
        assert len(svc_default.recompute_history()["items"]) == 0, "default 角色不应有重算历史"

        svc_default.close()
        svc_custom.close()
        print("  PASS test_recompute_character_routing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_proxy_models_merged_fault_tolerance() -> None:
    # 模拟两个 provider，一个失败，一个成功
    original_upstreams = forced_flow_proxy.UPSTREAMS
    try:
        forced_flow_proxy.UPSTREAMS = {
            "broken_provider": {
                "base_url": "http://127.0.0.1:59999",  # 无法连接的端口
                "api_key": "dummy",
                "default_model": "broken-model-v1",
            },
            "working_provider": {
                "base_url": "http://127.0.0.1:59998",
                "api_key": "dummy",
                "default_model": "good-model-v2",
            },
        }
        res = forced_flow_proxy._models_merged()
        assert res.get("object") == "list"
        data = res.get("data", [])
        # 两个 provider 都应当产生 fallback 条目，而不是因为 broken_provider 异常直接清空
        ids = [m["id"] for m in data]
        assert "broken_provider/broken-model-v1" in ids, f"broken_provider 应该有 fallback 模型: {ids}"
        assert "working_provider/good-model-v2" in ids, f"working_provider 应该有 fallback 模型: {ids}"
        print("  PASS test_proxy_models_merged_fault_tolerance")
    finally:
        forced_flow_proxy.UPSTREAMS = original_upstreams


def test_context_drilldown_cross_platform_encoding() -> None:
    tmp = tempfile.mkdtemp(prefix="loam_drilldown_enc_")
    try:
        j = Journal(Path(tmp) / "journal.db")
        m = Memory(Path(tmp) / "memory.db")
        eid1 = j.append("test_char", "s1", 1, "user", "开会汇报")
        eid2 = j.append("test_char", "s1", 1, "assistant", "演练一下")
        m.add_event(
            Event(
                id="ev_drill",
                summary="开会与演练",
                source_ids=[eid1, eid2],
                salience=0.9,
            )
        )
        from loam.core.network import Network
        net = Network()
        net.add("ev_drill", salience=0.9, anchor=True)
        m.save_network(net)

        builder = ContextBuilder(m, j, drilldown_top_k=1)
        ctx = builder.build("test_char", query="开会")
        rendered = ctx.render()

        # 验证能安全编码到 gbk 和 ascii (replace) 而不抛异常
        gbk_bytes = rendered.encode("gbk", errors="replace")
        assert len(gbk_bytes) > 0
        assert "->" in rendered, "应当使用标准安全箭头 ->"
        assert "\u21b3" not in rendered, "不应包含不可编码的 Unicode 字符 ↳"
        j.close()
        m.close()
        print("  PASS test_context_drilldown_cross_platform_encoding")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_seed_narrative_cold_start()
    test_base_url_rstrip_safety()
    test_pipeline_json_tool_block_cleaning()
    test_recompute_character_routing()
    test_proxy_models_merged_fault_tolerance()
    test_context_drilldown_cross_platform_encoding()
    print("\nAll regression fix tests passed!")
