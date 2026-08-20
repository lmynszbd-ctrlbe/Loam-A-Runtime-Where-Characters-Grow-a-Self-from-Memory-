# loam Release v0.2.0 — Checklist Closure (P0/P1/P2 All Green)

本发布用于对“P0/P1/P2 大清单”做收口交付：
- P0（上线前必须完成）：**17/17 ✅**
- P1（二期增强）：**14/14 ✅**
- P2（工程化与长期运维）：**7/7 ✅**

对应代码基线：`e480dbe09b46d249b5deec3d84b1400ffdb162c5`

---

## 1) Release Highlights

### A. 生产链路安全与稳定（P0）
- 并发统一锁（HTTP/CLI/Grower 不再并发踩库）
- ingest 异步持久队列 + 同 session 串行消费
- pending 证据落盘、重启恢复、幂等索引去重
- ingest → queue → commit 事务原子性
- learn 默认关闭（HTTP + CLI 对齐）
- 对外错误脱敏（request_id）
- API Key 鉴权可开关
- /healthz + /dashboard backlog 与告警分级

### B. 能力可解释与可演进（P1）
- 稳定 ID（事件/特质可复现）
- 时间窗聚合 + 稀疏桶归并
- 增量/全量重算与审计
- decay 仅作用派生权重层（不改原始真值）
- explainability 证据链可展开 source entries
- experiments flags 状态化 + 审计历史
- 低成本模型按 phase 路由
- 长会话分片抽取与分段归并
- 存储抽象层 Adapter（Pending/Job/Trait/Config）并扩大主路径接入
- SQLite→Postgres/TiKV 导出/回滚/一致性校验/演练闭环

### C. 工程化与运维完备度（P2）
- Dockerfile + docker-compose 模板
- requirements.lock + 可复现构建检查
- License/合规清单
- 备份/恢复/冷热归档脚本与 Runbook
- 压测与故障演练脚本
- 运维手册与报警 SOP
- CI 工作流（测试、迁移导出/加载/目标库一致性校验、docker build）

---

## 2) Full Checklist Matrix

### P0（上线前必须完成）
1. 并发模型统一锁（HTTP/CLI/Grower 不再并发踩库）—— ✅
2. ingest 异步任务队列持久化（ingest_jobs）—— ✅
3. 同 session 串行消费（队列内 per-session 单线程）—— ✅
4. learn=false 默认语义（不默认学习）—— ✅
5. 聊天 RAG 与成长 ingest 两条链路隔离 —— ✅
6. 去掉关键路径静默吞错（except: pass）—— ✅
7. 对外错误脱敏（不回堆栈，给 request_id）—— ✅
8. API Key 鉴权开关（可配置）—— ✅
9. /healthz + backlog 观测（pending/open_gaps/grower）—— ✅
10. pending 证据落盘 + 重启恢复 —— ✅
11. 幂等索引（UNIQUE(session_id,evidence_hash) 冲突即跳过）—— ✅
12. ingest→queue→commit 事务原子性 —— ✅
13. token 预算器（2200：软预算优先+硬上限兜底）—— ✅
14. 有效证据轻量规则过滤（寒暄/语气词/重复）—— ✅
15. top-k 限制、有限重试、降本参数固化 —— ✅
16. 参数回滚边界（只回滚配置，不改历史真值）—— ✅
17. 告警分级（info/warn/error）+ dashboard 展示 —— ✅

### P1（二期增强）
1. 稳定 ID 策略（事件/特质可复现）—— ✅
2. 时间窗口聚合（减少碎片）—— ✅
3. 增量重算 + 手动全量重算开关 —— ✅
4. decay 机制（衰减派生权重，不删原始真值）—— ✅
5. explainability（某次变化由哪些证据触发）—— ✅
6. 参数实验开关与审计记录 —— ✅
7. dashboard 任务态可视化增强 —— ✅
8. 成长链路与对话链路指标拆分 —— ✅
9. 低成本记忆模型接入策略 —— ✅
10. 长会话分片与分段归并 —— ✅
11. 存储抽象层（Journal/Pending/Job/Trait/Config Adapter）—— ✅
12. SQLite→Postgres/TiKV 迁移脚本 —— ✅
13. 迁移回滚脚本 + 一致性校验 —— ✅
14. 迁移压测演练流程 —— ✅

### P2（工程化与长期运维）
1. 容器化部署模板 —— ✅
2. 依赖版本锁定与构建可复现 —— ✅
3. License/合规清单 —— ✅
4. 压测与故障演练脚本 —— ✅
5. 备份恢复 Runbook —— ✅
6. 冷热归档（离线压缩备份，非删除主库）—— ✅
7. 运维手册与报警 SOP —— ✅

---

## 3) Validation Snapshot (this release)

已执行：
- `python -m compileall -q loam tests scripts`
- `for f in tests/test_*.py; do python "$f"; done`
- 迁移与运维脚本 help/可执行性检查（含新增目标库加载与目标一致性校验脚本）

结论：当前分支已完成 checklist 收口并通过本仓回归验证。

---

## 4) Release Publishing Notes (GitHub)

建议 Release Title：
- `v0.2.0 - Checklist Closure (P0/P1/P2 All ✅)`

建议附件/链接：
- `docs/RELEASE_v0.2.0_CHECKLIST_CLOSURE.md`（本页）
- `docs/MIGRATION_RUNBOOK.md`
- `docs/BACKUP_RESTORE_RUNBOOK.md`
- `docs/OPS_SOP.md`

---

## 5) Credits

- **@lmynszbd-ctrlbe** — Project owner, architecture lead, final release authority.
- **玉槿（AI 共创者）** — AI co-author (implementation assistance, checklist closure, beginner deployment documentation, release-note drafting).
- **all（AI 共创者）** — AI co-author (implementation assistance, refactoring support, test scaffolding).
