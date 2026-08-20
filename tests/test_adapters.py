"""存储抽象层 Adapter 测试。"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.store import Journal, Memory, SQLiteStorageAdapters


def test_sqlite_storage_adapters_basic():
    tmp = tempfile.mkdtemp()
    try:
        j = Journal(Path(tmp) / "journal.db")
        m = Memory(Path(tmp) / "memory.db")
        a = SQLiteStorageAdapters.from_instances(j, m)

        assert a.capabilities()["backend"] == "sqlite"

        a.pending.enqueue_pending_evidence(
            "阿萤",
            "s1",
            [{"turn": 1, "role": "user", "content": "hello"}],
        )
        stats = a.jobs.queue_stats("阿萤")
        assert stats["pending_evidence"] >= 1
        assert a.jobs.recover_processing_jobs("阿萤") >= 0

        flags = a.config.set_experiment_flags({"x": 1}, note="t", actor="tester")
        assert flags.get("x") == 1
        assert a.config.log_experiment_flags({"y": 2}, note="t2", actor="tester") > 0
    finally:
        j.close()
        m.close()
        shutil.rmtree(tmp)


if __name__ == "__main__":
    test_sqlite_storage_adapters_basic()
    print("PASS test_sqlite_storage_adapters_basic")