"""测试常数覆盖持久化与启动恢复机制。"""

from __future__ import annotations

import os
import shutil
import tempfile
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import loam.core.constants as C
from loam.core.state import (
    clear_persisted_overrides,
    load_persisted_overrides,
    overrides_file_path,
    save_persisted_overrides,
)
from loam.server import LoamService, ServiceConfig


def test_state_file_persistence() -> None:
    tmp_home = Path(tempfile.mkdtemp())
    try:
        items = {"PLASTICITY": {"original": 0.35, "override": 0.50}}
        ok = save_persisted_overrides(items, home=tmp_home, cycle=10)
        assert ok, "save_persisted_overrides should return True"
        
        loaded = load_persisted_overrides(home=tmp_home)
        assert "PLASTICITY" in loaded
        assert loaded["PLASTICITY"]["override"] == 0.50

        # clear
        clear_persisted_overrides(home=tmp_home)
        loaded_empty = load_persisted_overrides(home=tmp_home)
        assert loaded_empty == {}
    finally:
        shutil.rmtree(tmp_home, ignore_errors=True)
    print("  PASS test_state_file_persistence")


def test_service_restore_on_startup() -> None:
    tmp_home = Path(tempfile.mkdtemp())
    try:
        orig_plasticity = C.PLASTICITY
        cfg = ServiceConfig(
            character="test_bot",
            home=str(tmp_home / "characters"),
            auto_start_grower=False,
        )
        # 1. 启动服务并覆盖常数
        svc1 = LoamService(cfg)
        svc1.loam_home = tmp_home
        res = svc1.override_constants({"PLASTICITY": 0.48}, persist=True)
        assert res["applied"]["PLASTICITY"]["to"] == 0.48
        assert C.PLASTICITY == 0.48
        svc1.close()

        # 重置内存常数
        C.PLASTICITY = orig_plasticity

        # 2. 模拟 Watchdog 重启：新建服务实例，验证自动恢复
        svc2 = LoamService(cfg)
        svc2.loam_home = tmp_home
        # 手动触发生命周期内的恢复校验
        svc2._restore_persisted_constants()
        assert C.PLASTICITY == 0.48, "C.PLASTICITY should be restored to 0.48"
        assert "PLASTICITY" in svc2._runtime_const_overrides
        svc2.close()
    finally:
        C.PLASTICITY = 0.35  # restore default
        shutil.rmtree(tmp_home, ignore_errors=True)
    print("  PASS test_service_restore_on_startup")


if __name__ == "__main__":
    test_state_file_persistence()
    test_service_restore_on_startup()
    print("All persistence tests passed!")
