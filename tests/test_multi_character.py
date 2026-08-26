"""测试动态多角色卡路由支持 (Multi-Character Dynamic Routing)。"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loam.server import LoamHTTPServer, LoamService, ServiceConfig


def test_multi_character_dynamic_pool() -> None:
    tmp_home = tempfile.mkdtemp()
    cfg = ServiceConfig(character="default", home=tmp_home)
    service = LoamService(cfg)
    server = LoamHTTPServer(("127.0.0.1", 0), service)
    port = server.server_address[1]

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        # 1. 查询默认角色 health
        req1 = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req1) as r1:
            data1 = json.loads(r1.read().decode("utf-8"))
            assert data1["character"] == "default"

        # 2. 通过 Header 路由至新角色 "lin_daiyu"
        req2 = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        req2.add_header("X-Loam-Character", "lin_daiyu")
        with urllib.request.urlopen(req2) as r2:
            data2 = json.loads(r2.read().decode("utf-8"))
            assert data2["character"] == "lin_daiyu"

        # 3. 向 "lin_daiyu" 写入一条对话
        ingest_payload = {
            "session": "sess_lin",
            "turns": [{"turn": 1, "role": "user", "content": "林妹妹好呀，今天天气真好"}],
        }
        req3 = urllib.request.Request(
            f"http://127.0.0.1:{port}/ingest",
            data=json.dumps(ingest_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Loam-Character": "lin_daiyu"},
        )
        with urllib.request.urlopen(req3) as r3:
            res3 = json.loads(r3.read().decode("utf-8"))
            assert res3.get("character") == "lin_daiyu"
            assert res3.get("added") == 1

        # 4. 验证磁盘上已为 "lin_daiyu" 独立创建了数据库
        char_dir = Path(tmp_home) / "lin_daiyu"
        assert char_dir.exists()
        assert (char_dir / "journal.db").exists()
        assert (char_dir / "memory.db").exists()

        print("  PASS test_multi_character_dynamic_pool")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_multi_character_dynamic_pool()
    print("All multi-character tests passed!")