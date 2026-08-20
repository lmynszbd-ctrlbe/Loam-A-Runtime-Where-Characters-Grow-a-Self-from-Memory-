"""低成本记忆模型路由测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.mind.llm import Brain


class RecorderTransport:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        self.calls.append({"url": url, "payload": dict(payload), "timeout": timeout})
        return {
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


def test_low_cost_routing_by_phase():
    transport = RecorderTransport()
    b = Brain(
        api_key="primary-key",
        base_url="https://primary.example",
        model="primary-model",
        low_cost_api_key="cheap-key",
        low_cost_base_url="https://cheap.example",
        low_cost_model="cheap-model",
        low_cost_enabled=True,
        low_cost_phases=("extract", "observe"),
        transport=transport,
    )

    _ = b.ask_json("sys", "u1", phase="extract")
    _ = b.ask_json("sys", "u2", phase="appraise")

    c1, c2 = transport.calls
    assert c1["url"].startswith("https://cheap.example"), c1
    assert c1["payload"]["model"] == "cheap-model"
    assert c1["payload"]["_api_key"] == "cheap-key"

    assert c2["url"].startswith("https://primary.example"), c2
    assert c2["payload"]["model"] == "primary-model"
    assert c2["payload"]["_api_key"] == "primary-key"

    usage = b.usage.as_dict()
    routes = usage.get("路由调用") or {}
    assert routes.get("low_cost:extract") == 1
    assert routes.get("primary") == 1


if __name__ == "__main__":
    test_low_cost_routing_by_phase()
    print("PASS test_low_cost_routing_by_phase")