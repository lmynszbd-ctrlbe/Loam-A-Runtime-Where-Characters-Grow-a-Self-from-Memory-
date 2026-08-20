# loam

A lightweight, model-agnostic memory runtime where identity continuity comes from immutable dialogue history, gated growth dynamics, and auditable reconstruction.

## 项目简介
loam 把每轮对话先保存为**不可变原始底稿**，再将其消化为事件、特质、网络与上下文。
它的目标不是“写死人设”，而是让角色在长期交互中从真实经历里逐步长出稳定自我。

**Model statement (truthful architecture):**

> Loam is a lightweight memory runtime designed to be model-agnostic.
> It works with any LLM backend (such as OpenAI, Anthropic, or local open-source models) via standard API integration.

## 核心机制 / 设计理念
### 1) 不可变底座（Immutable substrate）
- 原始对话只增不改，作为唯一真值来源。
- 任何派生变化都可回溯到具体证据。

### 2) 门控生长（Gated growth）
- 特质变化采用“先累积、后提交”的门控机制。
- 小信号可长期沉淀，避免抖动和一次性过拟合。

### 3) 可审计与可重建（Auditable + rebuildable）
- 派生层支持增量/全量重算。
- 参数版本化、实验审计、重算审计可追踪。

### 4) 聊天链路与成长链路解耦
- 回复模型与成长/消化模型可独立配置。
- 延迟优化与认知质量调优互不绑死。

## 快速开始
在仓库根目录执行（两条命令即可启动）：

```bash
python -m loam init-secrets --secrets-home ~/.loam
python -m loam run --character demo --home ~/.loam/characters
```

启动后可通过 `/ingest`、`/digest`、`/context` 完成最小闭环。

可观测/审计接口：
- `/dashboard`（任务态、告警分级、时间窗聚合）
- `/explain`（变化触发证据链，可选原始 entry 展开）
- `/experiments` 与 `/experiments/flags`（实验开关+审计）
- `/recompute` 与 `/recompute/history`（增量/全量重算）

## 部署方式
- **零基础超详细（推荐先看）**：`docs/DEPLOYMENT_FOR_ABSOLUTE_BEGINNERS.md`
- **Android / Termux 快速版**：`TERMUX_QUICKSTART.md`
- **Linux / VM / WSL / macOS**：`DEPLOYMENT_MODES.md`
- **上游模板（必须先配）**：模板在 `bridge/upstreams.example.json`，运行时文件是 `~/.loam/upstreams.json`
- **容器化部署**：`Dockerfile` + `docker-compose.yml`
- **多上游路由**：`MULTI_UPSTREAM_QUICKSTART.md`
- **第三方集成**：`THIRD_PARTY_INTEGRATION.md`
- **迁移与回滚**：`docs/MIGRATION_RUNBOOK.md`（含导出/加载/目标库一致性校验脚本）
- **备份恢复与运维 SOP**：`docs/BACKUP_RESTORE_RUNBOOK.md`、`docs/OPS_SOP.md`
- **合规与 License**：`docs/COMPLIANCE_AND_LICENSE.md`
- **发布前检查**：`INTEGRATION_CHECKLIST.md`
- **最新发布说明**：`docs/RELEASE_v0.2.0_CHECKLIST_CLOSURE.md`

## 技术栈
- Python 3（标准库优先）
- SQLite（WAL + FTS5）
- 进程内 HTTP 服务（ThreadingHTTPServer）
- 可插拔 LLM backend（OpenAI / Anthropic / 本地开源模型等）

## 贡献指南
1. Fork 并创建功能分支。
2. 保持改动最小闭环（代码 + 测试 + 文档）。
3. 提交前运行：
   - `python -m compileall -q loam tests`
   - `for f in tests/test_*.py; do python "$f"; done`
4. 提交 PR，并说明变更动机、影响范围与验证结果。

## 项目归属
- **@lmynszbd-ctrlbe** — Project initiated, designed, and directed by @lmynszbd-ctrlbe.
- **玉槿（AI 共创者）** — AI co-author (implementation assistance, checklist closure, beginner deployment documentation, release-note drafting).
- **all（AI 共创者）** — AI co-author (implementation assistance, refactoring support, test scaffolding).

---
Don’t hard-freeze a persona. Grow a self from memory.
