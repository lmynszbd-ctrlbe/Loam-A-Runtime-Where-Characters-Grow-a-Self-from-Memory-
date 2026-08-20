# P1/P2 Delivery Report (this round)

## P1（二期增强）

1. ✅ 稳定 ID 策略（事件/特质可复现）
   - `loam/mind/digest.py` stable event id + trait id
2. ✅ 时间窗口聚合（减少碎片）
   - `Memory.event_window_stats()` 新增 `merged_points` + `fragment_ratio`
3. ✅ 增量重算 + 手动全量重算开关
   - `/recompute` + `/recompute/history`
4. ✅ decay 机制（衰减派生权重，不删原始真值）
   - `event_decay` + runtime decay controls
5. ✅ explainability（某次变化由哪些证据触发）
   - `/explain` 支持 `include_entries`，可展开 `source_entries`
6. ✅ 参数实验开关与审计记录
   - `/experiments/flags` + `/experiments/flags/update`
   - `Memory.experiment_flags()/set_experiment_flags()`
7. ✅ dashboard 任务态可视化增强
   - `/dashboard.tasks`：grower/ingest_queue/digest/extract
8. ✅ 成长链路与对话链路指标拆分
   - `dialog.*` vs `growth.*` metrics
9. ✅ 低成本记忆模型接入策略
   - `Brain` 支持 phase-based low-cost routing
   - runtime toggle: `brain.low_cost_enabled`
10. ✅ 长会话分片与分段归并
   - digest extract sharding + merge pipeline
11. ✅ 存储抽象层（Adapter）
   - `loam/store/adapters.py`
12. ✅ SQLite→Postgres/TiKV 迁移脚本
   - `scripts/migration/sqlite_to_postgres_tikv.py`
13. ✅ 迁移回滚脚本 + 一致性校验
   - `scripts/migration/rollback_from_snapshot.py`
   - `scripts/migration/verify_migration_consistency.py`
14. ✅ 迁移压测演练流程
   - `scripts/migration/rehearse_migration_load.py`

## P2（工程化与长期运维）本轮完成部分

1. ✅ 容器化部署模板
   - `Dockerfile`, `docker-compose.yml`
2. ✅ 依赖版本锁定与构建可复现
   - `requirements.lock`, `scripts/ops/check_reproducible_build.sh`
3. ✅ License/合规清单
   - `LICENSE`, `docs/COMPLIANCE_AND_LICENSE.md`
4. ✅ 压测与故障演练脚本
   - `scripts/ops/load_and_fault_drill.py`
5. ✅ 备份恢复 Runbook
   - `docs/BACKUP_RESTORE_RUNBOOK.md`
   - `scripts/ops/create_snapshot.py`, `scripts/ops/restore_snapshot.py`
6. ✅ 冷热归档（离线压缩备份）
   - `scripts/ops/archive_cold_snapshots.py`
7. ✅ 运维手册与报警 SOP
   - `docs/OPS_SOP.md`

## 验证

- `python -m compileall -q loam tests scripts`
- `for f in tests/test_*.py; do python "$f"; done`
- `python scripts/verify_three_dialogues_trait_shift.py`
- migration smoke:
  - `sqlite_to_postgres_tikv.py`
  - `verify_migration_consistency.py`
  - `rehearse_migration_load.py`
- ops smoke:
  - `create_snapshot.py`
  - `restore_snapshot.py --dry-run`
  - `load_and_fault_drill.py`