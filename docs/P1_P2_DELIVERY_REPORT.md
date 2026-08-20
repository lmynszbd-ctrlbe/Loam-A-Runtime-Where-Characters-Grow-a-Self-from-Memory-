# Delivery Checklist Status (P0 / P1 / P2)

标记说明：
- ✅ 已完成
- 🟡 部分完成（先止血，后续补全）
- ⏳ 未开始

## P0（上线前必须完成）

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

## P1（二期增强）

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

## P2（工程化与长期运维）

1. 容器化部署模板 —— ✅
2. 依赖版本锁定与构建可复现 —— ✅
3. License/合规清单 —— ✅
4. 压测与故障演练脚本 —— ✅
5. 备份恢复 Runbook —— ✅
6. 冷热归档（离线压缩备份，非删除主库）—— ✅
7. 运维手册与报警 SOP —— ✅

## 主要落地文件（节选）

- 路由与低成本策略：`loam/mind/llm.py`
- 分片抽取与归并：`loam/mind/digest.py`
- 运行时开关、dashboard/explain API：`loam/server.py`
- 队列/作业/实验开关存储：`loam/store/journal.py`, `loam/store/memory.py`
- 存储抽象层：`loam/store/adapters.py`
- 迁移与回滚：`scripts/migration/*`
- 运维与备份演练：`scripts/ops/*`
- 容器化：`Dockerfile`, `docker-compose.yml`
- 合规文档：`LICENSE`, `docs/COMPLIANCE_AND_LICENSE.md`