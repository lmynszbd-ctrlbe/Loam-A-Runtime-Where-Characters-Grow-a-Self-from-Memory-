"""测试第三阶段：消息三通道分流管道 & 记忆原矿下钻系统。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loam.mind.context import ContextBuilder
from loam.mind.pipeline import parse_turn_channels, sanitize_turns_for_ingest
from loam.core.network import Network
from loam.store.journal import Journal
from loam.store.memory import Event, Memory


def test_pipeline_three_channels_parsing() -> None:
    # 1. 纯思考 + 对话 + 工具调用
    raw = (
        "<think>用户心情不好，我应该温柔安慰。</think>"
        "别难过啦，抱抱你！"
        "<tool_call>{\"name\": \"send_flower\", \"args\": {\"type\": \"rose\"}}</tool_call>"
    )
    parsed = parse_turn_channels("assistant", raw)
    assert parsed.thought == "用户心情不好，我应该温柔安慰。"
    assert parsed.dialogue == "别难过啦，抱抱你！"
    assert len(parsed.actions) == 1
    assert parsed.actions[0].get("name") == "send_flower"

    # 2. 批量清洗
    turns = [
        {"turn": 1, "role": "user", "content": "帮我查一下天气"},
        {
            "turn": 2,
            "role": "assistant",
            "content": "<think>要调天气工具</think>正在为你查询今天的天气<tool_call>{\"tool\":\"get_weather\"}</tool_call>",
        },
    ]
    sanitized, stats = sanitize_turns_for_ingest(turns)
    assert len(sanitized) == 2
    assert sanitized[1]["content"] == "正在为你查询今天的天气"
    assert "thought_preview" in sanitized[1]["meta"]
    assert "actions" in sanitized[1]["meta"]
    assert stats["has_thought"] == 1
    assert stats["has_action"] == 1
    print("  PASS test_pipeline_three_channels_parsing")


def test_context_drilldown_l0_raw() -> None:
    tmp_dir = tempfile.mkdtemp()
    try:
        j_path = Path(tmp_dir) / "journal.db"
        m_path = Path(tmp_dir) / "memory.db"

        journal = Journal(j_path)
        memory = Memory(m_path)

        # 写入原始对话 entry
        e1_id = journal.append("崽崽", "sess_1", 1, "user", "今天天气真好，去公园散步了")
        e2_id = journal.append("崽崽", "sess_1", 2, "assistant", "哇，公园的花开得很漂亮吧！")

        # 写入由该对话沉淀的 Event
        memory.add_event(
            Event(
                id="ev_walk",
                summary="两人聊了公园散步和花开",
                source_ids=[e1_id, e2_id],
                salience=0.8,
                session="sess_1",
            )
        )

        net = Network()
        net.add("ev_walk", salience=0.8, anchor=True)
        memory.save_network(net)

        # 装配 Context（带下钻功能）
        builder = ContextBuilder(memory=memory, journal=journal, drilldown_top_k=1)
        pack = builder.build("崽崽", query="散步", learn=False)

        assert len(pack.recalled) > 0
        rec = pack.recalled[0]
        assert rec["id"] == "ev_walk"
        assert "drilldown" in rec
        assert len(rec["drilldown"]) == 2
        assert rec["drilldown"][0]["content"] == "今天天气真好，去公园散步了"

        rendered = pack.render()
        assert "[L0 现场]" in rendered
        assert "今天天气真好" in rendered
        print("  PASS test_context_drilldown_l0_raw")
    finally:
        journal.close()
        memory.close()


if __name__ == "__main__":
    test_pipeline_three_channels_parsing()
    test_context_drilldown_l0_raw()
    print("All third stage tests passed!")