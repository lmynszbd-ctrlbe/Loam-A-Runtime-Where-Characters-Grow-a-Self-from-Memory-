"""loam 本地 HTTP 服务。

原则：
- 纯标准库，可在云机/本机/Termux 直接跑。
- API 很薄：收料、消化、拿上下文、看状态。
- 进程内自带后台成长线程（可开可关）。
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .mind.context import ContextBuilder
from .mind.digest import Digester, Grower
from .mind.llm import Brain, load_brain
from .store.adapters import SQLiteStorageAdapters
from .store.journal import MAX_INGEST_JOB_ATTEMPTS, Journal
from .store.memory import Memory


@dataclass
class ServiceConfig:
    character: str = "default"
    home: str = "~/.loam/characters"
    default_session: str = "default"
    batch_turns: int = 20
    grow_interval: float = 60.0
    idle_seconds: float = 900.0
    audit_every: int = 50
    auto_start_grower: bool = True
    api_key: str = ""


_RUNTIME_CONFIG_DEFAULTS: Dict[str, object] = {
    # 上下文 top-k 与预算
    "context.max_matches": 8,
    "context.max_recall": 16,
    "context.max_traits": 12,
    "context.trait_floor": 0.2,
    "context.soft_token_budget": 2200,
    "context.hard_token_budget": 2600,
    # 成本控制与请求上界
    "ingest.max_turns_per_request": 80,
    "ingest.max_content_chars": 3000,
    "queue.max_sync_jobs": 1,
    "queue.max_drain_jobs": 8,
    "digest.max_limit": 80,
    "drain.max_rounds": 100,
    "queue.max_retry_attempts": MAX_INGEST_JOB_ATTEMPTS,
    # 长会话分片抽取（减少超长 transcript 碎片）
    "digest.segment.max_entries": 24,
    "digest.segment.max_turn_span": 12,
    # 时间窗口聚合（dashboard）
    "dashboard.window_seconds": 86400,
    "dashboard.bucket_seconds": 3600,
    # 事件衰减（仅派生权重层）
    "decay.enabled": True,
    "decay.half_life_hours": 72.0,
    "decay.min_weight": 0.25,
    "decay.stood_firm_floor": 0.55,
    "decay.apply_interval_seconds": 300,
    # 低成本记忆模型路由与 explainability 开关
    "brain.low_cost_enabled": False,
    "experiment.explain.include_raw_entries": True,
    # 重算
    "recompute.max_rounds": 400,
}


class LoamService:
    """进程内核心服务。HTTP 和 CLI 都调它。"""

    def __init__(self, config: ServiceConfig, brain: Optional[Brain] = None) -> None:
        self.config = config
        self.character = config.character
        self.root = Path(config.home).expanduser() / self.character
        self.root.mkdir(parents=True, exist_ok=True)

        self.journal = Journal(self.root / "journal.db")
        self.memory = Memory(self.root / "memory.db")
        self.adapters = SQLiteStorageAdapters.from_instances(self.journal, self.memory)
        self.brain = brain or load_brain()
        self.api_key = (config.api_key or os.environ.get("LOAM_API_KEY", "")).strip()

        # 崩溃恢复：把遗留 processing 队列任务恢复为 pending。
        self.adapters.jobs.recover_processing_jobs(self.character)
        self.digester = Digester(
            self.character,
            self.journal,
            self.memory,
            self.brain,
            batch_turns=config.batch_turns,
            pending_adapter=self.adapters.pending,
            job_adapter=self.adapters.jobs,
            trait_adapter=self.adapters.traits,
        )

        # 运行参数：支持版本化与配置回滚（只影响行为参数，不改历史真值）。
        self._runtime_config = self._bootstrap_runtime_config()
        self.context = self._build_context_builder(self._runtime_config)
        self._apply_runtime_switches(self._runtime_config)

        # 所有 journal/memory 操作都走同一把锁，避免 HTTP 请求与后台 grower 竞态。
        self._lock = threading.RLock()


        self.grower = Grower(
            self.digester,
            interval=config.grow_interval,
            idle_seconds=config.idle_seconds,
            audit_every=config.audit_every,
            step_lock=self._lock,
        )

        if config.auto_start_grower:
            self.grower.start()

    def _bootstrap_runtime_config(self) -> Dict[str, object]:
        current = self.adapters.config.runtime_config()
        normalized = self._coerce_runtime_config(current)
        if not current:
            self.adapters.config.set_runtime_config(
                normalized,
                note="bootstrap defaults",
                actor="bootstrap",
            )
        elif normalized != current:
            self.adapters.config.set_runtime_config(
                normalized,
                note="normalize config",
                actor="bootstrap",
            )
        return normalized

    def _coerce_runtime_config(self, raw: Dict[str, object]) -> Dict[str, object]:
        cfg: Dict[str, object] = dict(_RUNTIME_CONFIG_DEFAULTS)

        cfg["context.max_matches"] = _clamp_int(raw.get("context.max_matches"), int(cfg["context.max_matches"]), 1, 32)
        cfg["context.max_recall"] = _clamp_int(raw.get("context.max_recall"), int(cfg["context.max_recall"]), 1, 64)
        cfg["context.max_traits"] = _clamp_int(raw.get("context.max_traits"), int(cfg["context.max_traits"]), 1, 24)
        cfg["context.trait_floor"] = _clamp_float(raw.get("context.trait_floor"), float(cfg["context.trait_floor"]), 0.0, 1.0)
        cfg["context.soft_token_budget"] = _clamp_int(raw.get("context.soft_token_budget"), int(cfg["context.soft_token_budget"]), 200, 6000)
        cfg["context.hard_token_budget"] = _clamp_int(raw.get("context.hard_token_budget"), int(cfg["context.hard_token_budget"]), int(cfg["context.soft_token_budget"]), 8000)

        cfg["ingest.max_turns_per_request"] = _clamp_int(raw.get("ingest.max_turns_per_request"), int(cfg["ingest.max_turns_per_request"]), 1, 500)
        cfg["ingest.max_content_chars"] = _clamp_int(raw.get("ingest.max_content_chars"), int(cfg["ingest.max_content_chars"]), 64, 20000)

        cfg["queue.max_sync_jobs"] = _clamp_int(raw.get("queue.max_sync_jobs"), int(cfg["queue.max_sync_jobs"]), 0, 8)
        cfg["queue.max_drain_jobs"] = _clamp_int(raw.get("queue.max_drain_jobs"), int(cfg["queue.max_drain_jobs"]), 1, 64)
        cfg["digest.max_limit"] = _clamp_int(raw.get("digest.max_limit"), int(cfg["digest.max_limit"]), 1, 500)
        cfg["drain.max_rounds"] = _clamp_int(raw.get("drain.max_rounds"), int(cfg["drain.max_rounds"]), 1, 1000)
        cfg["queue.max_retry_attempts"] = MAX_INGEST_JOB_ATTEMPTS
        cfg["digest.segment.max_entries"] = _clamp_int(raw.get("digest.segment.max_entries"), int(cfg["digest.segment.max_entries"]), 8, 240)
        cfg["digest.segment.max_turn_span"] = _clamp_int(raw.get("digest.segment.max_turn_span"), int(cfg["digest.segment.max_turn_span"]), 2, 240)

        cfg["dashboard.window_seconds"] = _clamp_int(raw.get("dashboard.window_seconds"), int(cfg["dashboard.window_seconds"]), 3600, 3600 * 24 * 30)
        cfg["dashboard.bucket_seconds"] = _clamp_int(raw.get("dashboard.bucket_seconds"), int(cfg["dashboard.bucket_seconds"]), 60, int(cfg["dashboard.window_seconds"]))

        cfg["decay.enabled"] = _coerce_bool(raw.get("decay.enabled"), default=bool(cfg["decay.enabled"]))
        cfg["decay.half_life_hours"] = _clamp_float(raw.get("decay.half_life_hours"), float(cfg["decay.half_life_hours"]), 0.1, 24.0 * 365.0)
        cfg["decay.min_weight"] = _clamp_float(raw.get("decay.min_weight"), float(cfg["decay.min_weight"]), 0.0, 1.0)
        cfg["decay.stood_firm_floor"] = _clamp_float(raw.get("decay.stood_firm_floor"), float(cfg["decay.stood_firm_floor"]), float(cfg["decay.min_weight"]), 1.0)
        cfg["decay.apply_interval_seconds"] = _clamp_int(raw.get("decay.apply_interval_seconds"), int(cfg["decay.apply_interval_seconds"]), 0, 3600 * 24)

        cfg["brain.low_cost_enabled"] = _coerce_bool(raw.get("brain.low_cost_enabled"), default=bool(cfg["brain.low_cost_enabled"]))
        cfg["experiment.explain.include_raw_entries"] = _coerce_bool(
            raw.get("experiment.explain.include_raw_entries"),
            default=bool(cfg["experiment.explain.include_raw_entries"]),
        )

        cfg["recompute.max_rounds"] = _clamp_int(raw.get("recompute.max_rounds"), int(cfg["recompute.max_rounds"]), 1, 5000)
        return cfg

    def _build_context_builder(self, cfg: Dict[str, object]) -> ContextBuilder:
        return ContextBuilder(
            self.memory,
            max_matches=int(cfg["context.max_matches"]),
            max_recall=int(cfg["context.max_recall"]),
            max_traits=int(cfg["context.max_traits"]),
            trait_floor=float(cfg["context.trait_floor"]),
            soft_token_budget=int(cfg["context.soft_token_budget"]),
            hard_token_budget=int(cfg["context.hard_token_budget"]),
        )

    def _apply_runtime_switches(self, cfg: Dict[str, object]) -> None:
        """把运行参数中的开关同步到运行中组件。"""
        # Digester 分片参数
        self.digester.segment_max_entries = int(cfg.get("digest.segment.max_entries", 24) or 24)
        self.digester.segment_max_turn_span = int(cfg.get("digest.segment.max_turn_span", 12) or 12)

        # 低成本记忆模型路由开关
        enabled = _coerce_bool(cfg.get("brain.low_cost_enabled"), default=False)
        if hasattr(self.brain, "set_low_cost_enabled"):
            try:
                self.brain.set_low_cost_enabled(enabled)
            except Exception:  # noqa: BLE001
                pass

    def runtime_config(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current": dict(self._runtime_config),
                "version": int(self.memory.get_state("runtime_config_version", "0") or 0),
                "history": self.adapters.config.runtime_config_history(limit=20),
            }

    def update_runtime_config(self, updates: Dict[str, Any], note: str = "") -> Dict[str, Any]:
        with self._lock:
            if not updates:
                raise ValueError("updates 不能为空")
            unknown = sorted([k for k in updates.keys() if k not in _RUNTIME_CONFIG_DEFAULTS])
            if unknown:
                raise ValueError(f"未知配置项: {', '.join(unknown)}")

            merged = dict(self._runtime_config)
            merged.update(updates)
            normalized = self._coerce_runtime_config(merged)
            note_text = note.strip() or "manual update"
            version_id = self.adapters.config.set_runtime_config(
                normalized,
                note=note_text,
                actor="api",
            )
            self.adapters.config.log_experiment_flags(updates, note=note_text, actor="api")
            self._runtime_config = normalized
            self.context = self._build_context_builder(self._runtime_config)
            self._apply_runtime_switches(self._runtime_config)
            return {
                "ok": True,
                "version": version_id,
                "current": dict(self._runtime_config),
            }

    def rollback_runtime_config(self, version_id: int, note: str = "") -> Dict[str, Any]:
        with self._lock:
            note_text = note.strip() or "manual rollback"
            cfg = self.adapters.config.rollback_runtime_config(
                int(version_id),
                note=note_text,
                actor="api",
            )
            self.adapters.config.log_experiment_flags(
                {"rollback_to_version": int(version_id)},
                note=note_text,
                actor="api",
            )
            self._runtime_config = self._coerce_runtime_config(cfg)
            self.context = self._build_context_builder(self._runtime_config)
            self._apply_runtime_switches(self._runtime_config)
            return {
                "ok": True,
                "source_version": int(version_id),
                "version": int(self.memory.get_state("runtime_config_version", "0") or 0),
                "current": dict(self._runtime_config),
            }

    def _metric_inc(self, key: str, delta: int = 1) -> None:
        state_key = f"metric:{key}"
        cur = _safe_int(self.memory.get_state(state_key, "0"), 0)
        nxt = max(0, cur + int(delta))
        self.memory.set_state(state_key, str(nxt))

    def _metric_get(self, key: str) -> int:
        return _safe_int(self.memory.get_state(f"metric:{key}", "0"), 0)

    def _pipeline_metrics(self) -> Dict[str, Dict[str, int]]:
        return {
            "dialog": {
                "context_requests": self._metric_get("dialog.context_requests"),
                "context_learn_requests": self._metric_get("dialog.context_learn_requests"),
            },
            "growth": {
                "ingest_requests": self._metric_get("growth.ingest_requests"),
                "digest_requests": self._metric_get("growth.digest_requests"),
                "drain_requests": self._metric_get("growth.drain_requests"),
                "queue_jobs_done": self._metric_get("growth.queue_jobs_done"),
                "queue_jobs_failed": self._metric_get("growth.queue_jobs_failed"),
                "dropped_lightweight": self._metric_get("growth.dropped_lightweight"),
                "overflow_trimmed_turns": self._metric_get("growth.overflow_trimmed_turns"),
            },
        }

    def _maybe_apply_decay_unlocked(self, force: bool = False) -> Dict[str, Any]:
        enabled = bool(self._runtime_config.get("decay.enabled", True))
        if not enabled:
            return {"enabled": False, "applied": False, "reason": "disabled"}

        now = time.time()
        interval = int(self._runtime_config.get("decay.apply_interval_seconds", 300) or 0)
        last = 0.0
        try:
            last = float(self.memory.get_state("decay:last_applied_at", "0") or 0.0)
        except ValueError:
            last = 0.0

        if not force and interval > 0 and (now - last) < interval:
            return {
                "enabled": True,
                "applied": False,
                "last_applied_at": last,
                "next_after_seconds": max(0, int(interval - (now - last))),
            }

        info = self.memory.apply_event_decay(
            half_life_hours=float(self._runtime_config.get("decay.half_life_hours", 72.0) or 72.0),
            min_weight=float(self._runtime_config.get("decay.min_weight", 0.25) or 0.25),
            stood_firm_floor=float(self._runtime_config.get("decay.stood_firm_floor", 0.55) or 0.55),
            now=now,
        )
        self.memory.set_state("decay:last_applied_at", str(now))
        return {
            "enabled": True,
            "applied": True,
            "last_applied_at": now,
            **info,
        }

    def recompute(self, mode: str = "incremental", max_rounds: Optional[int] = None, note: str = "") -> Dict[str, Any]:
        with self._lock:
            picked = str(mode or "incremental").strip().lower()
            if picked not in {"incremental", "full"}:
                raise ValueError("mode 仅支持 incremental/full")

            from_cycle = int(self.memory.get_state("cycle", "0") or 0)
            run_id = self.memory.begin_recompute_run(
                mode=picked,
                trigger="api",
                from_cycle=from_cycle,
                details={"note": note.strip()},
            )

            details: Dict[str, Any] = {}
            was_alive = self.grower.alive
            try:
                if picked == "incremental":
                    details["reindexed"] = int(self.memory.reindex())
                    details["decay"] = self._maybe_apply_decay_unlocked(force=True)
                else:
                    if was_alive:
                        self.grower.stop()

                    self.memory.wipe_derived()
                    reset_entries = self.journal.reset_digestion(self.character)
                    limit = int(max_rounds) if max_rounds is not None else int(self._runtime_config["recompute.max_rounds"])
                    safe_rounds = max(1, min(limit, int(self._runtime_config["recompute.max_rounds"])))
                    reports = self.grower.drain(max_rounds=safe_rounds)
                    details = {
                        "reset_entries": int(reset_entries),
                        "rounds": len(reports),
                        "events": sum(r.events for r in reports),
                        "errors": [err for r in reports for err in r.errors][:20],
                        "pending_after": self.digester.pending_count(),
                    }
                    details["decay"] = self._maybe_apply_decay_unlocked(force=True)

                to_cycle = int(self.memory.get_state("cycle", "0") or 0)
                self.memory.finish_recompute_run(run_id, status="ok", details=details, to_cycle=to_cycle)
                return {
                    "ok": True,
                    "run_id": run_id,
                    "mode": picked,
                    "from_cycle": from_cycle,
                    "to_cycle": to_cycle,
                    "details": details,
                }
            except Exception as exc:  # noqa: BLE001
                details["error"] = str(exc)
                to_cycle = int(self.memory.get_state("cycle", "0") or 0)
                self.memory.finish_recompute_run(run_id, status="failed", details=details, to_cycle=to_cycle)
                raise
            finally:
                if picked == "full" and was_alive and self.config.auto_start_grower:
                    self.grower.start()

    def recompute_history(self, limit: int = 20) -> Dict[str, Any]:
        with self._lock:
            return {
                "items": self.memory.recompute_history(limit=max(1, min(int(limit), 200)))
            }

    def experiment_history(self, limit: int = 20) -> Dict[str, Any]:
        with self._lock:
            return {
                "current": self.adapters.config.experiment_flags(),
                "items": self.adapters.config.experiment_history(limit=max(1, min(int(limit), 200))),
            }

    def experiment_flags(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current": self.adapters.config.experiment_flags(),
                "items": self.adapters.config.experiment_history(limit=20),
            }

    def update_experiment_flags(self, flags: Dict[str, Any], note: str = "", merge: bool = True) -> Dict[str, Any]:
        with self._lock:
            if not isinstance(flags, dict) or not flags:
                raise ValueError("flags 必须是非空对象")
            note_text = note.strip() or "experiment update"
            current = self.adapters.config.set_experiment_flags(
                flags,
                note=note_text,
                actor="api",
                merge=merge,
            )

            # 允许实验开关直连低成本模型路由。
            if "brain.low_cost_enabled" in current:
                self._runtime_config["brain.low_cost_enabled"] = _coerce_bool(
                    current.get("brain.low_cost_enabled"),
                    default=bool(self._runtime_config.get("brain.low_cost_enabled", False)),
                )
                self._apply_runtime_switches(self._runtime_config)

            return {
                "ok": True,
                "current": current,
                "items": self.adapters.config.experiment_history(limit=20),
            }

    def _build_alerts(self, queue: Dict[str, int], pending: int, open_gaps: int) -> Dict[str, Any]:
        alerts: List[Dict[str, Any]] = []

        if self.config.auto_start_grower and not self.grower.alive:
            alerts.append({"level": "error", "code": "grower_down", "message": "grower 未运行"})
        if int(queue.get("jobs_failed", 0)) > 0:
            alerts.append({
                "level": "error",
                "code": "queue_failed",
                "message": f"ingest 队列失败任务 {int(queue.get('jobs_failed', 0))} 条",
            })
        if self.grower.last_error:
            alerts.append({"level": "warn", "code": "grower_last_error", "message": "grower 最近一次执行有异常"})
        if open_gaps > 0:
            alerts.append({"level": "warn", "code": "open_gaps", "message": f"还有 {open_gaps} 个漏轮缺口未补齐"})
        if int(queue.get("pending_evidence", 0)) > 120 or pending > 240:
            alerts.append({"level": "warn", "code": "backlog_high", "message": "待处理 backlog 偏高"})

        if not alerts:
            alerts.append({"level": "info", "code": "healthy", "message": "流水线运行正常"})

        counts = {
            "info": sum(1 for a in alerts if a["level"] == "info"),
            "warn": sum(1 for a in alerts if a["level"] == "warn"),
            "error": sum(1 for a in alerts if a["level"] == "error"),
        }
        level = "error" if counts["error"] else ("warn" if counts["warn"] else "info")
        return {"level": level, "counts": counts, "items": alerts}

    def _dashboard_unlocked(self) -> Dict[str, Any]:
        queue = self.adapters.jobs.queue_stats(self.character)
        pending = self.digester.pending_count()
        open_gaps = len(self.journal.open_gaps(self.character))
        decay = self._maybe_apply_decay_unlocked(force=False)

        window_seconds = int(self._runtime_config.get("dashboard.window_seconds", 86400) or 86400)
        bucket_seconds = int(self._runtime_config.get("dashboard.bucket_seconds", 3600) or 3600)
        events_window = self.memory.event_window_stats(
            window_seconds=window_seconds,
            bucket_seconds=bucket_seconds,
            limit=64,
        )
        changes_window = self.memory.changelog_window_stats(
            window_seconds=window_seconds,
            bucket_seconds=bucket_seconds,
            limit=64,
        )

        extract_segments = _safe_int(self.memory.get_state("extract:last_segments", "0"), 0)
        extract_raw = _safe_int(self.memory.get_state("extract:last_events_raw", "0"), 0)
        extract_merged = _safe_int(self.memory.get_state("extract:last_events_merged", "0"), 0)
        last_digest_at = float(self.memory.get_state("last_digest_at", "0") or 0.0)

        return {
            "backlog": {
                "pending": pending,
                "open_gaps": open_gaps,
                "queue": queue,
            },
            "alerts": self._build_alerts(queue, pending, open_gaps),
            "metrics": self._pipeline_metrics(),
            "runtime_config": {
                "version": int(self.memory.get_state("runtime_config_version", "0") or 0),
                "current": dict(self._runtime_config),
            },
            "experiments": self.adapters.config.experiment_flags(),
            "windows": {
                "events": events_window,
                "changes": changes_window,
            },
            "tasks": {
                "grower": {
                    "alive": self.grower.alive,
                    "last_error": self.grower.last_error,
                    "last_step_at": float(getattr(self.grower, "last_step_at", 0.0) or 0.0),
                    "reports_cached": len(self.grower.reports),
                },
                "ingest_queue": {
                    "sessions": self.adapters.jobs.queue_sessions(self.character, limit=12),
                    "recent_jobs": self.adapters.jobs.recent_ingest_jobs(self.character, limit=12),
                },
                "digest": {
                    "cycle": int(self.memory.get_state("cycle", "0") or 0),
                    "last_digest_at": last_digest_at,
                    "idle_seconds": float(self.config.idle_seconds),
                    "ready_now": self.digester.ready(idle_seconds=float(self.config.idle_seconds)),
                },
                "extract": {
                    "last_segments": extract_segments,
                    "last_events_raw": extract_raw,
                    "last_events_merged": extract_merged,
                    "merge_saved": max(0, extract_raw - extract_merged),
                },
            },
            "decay": decay,
            "recent": {
                "recompute": self.memory.recompute_history(limit=5),
                "experiments": self.adapters.config.experiment_history(limit=5),
            },
        }

    def narrative(self) -> Dict[str, Any]:
        with self._lock:
            n = self.memory.current_narrative()
            return {
                "text": str(n.get("text", "")) if n else "",
                "cycle": int(n.get("cycle", 0)) if n else 0,
            }

    def dashboard(self) -> Dict[str, Any]:
        with self._lock:
            return self._dashboard_unlocked()

    def explain(self, kind: str = "", limit: int = 20, include_entries: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            self._maybe_apply_decay_unlocked(force=False)
            rows = self.memory.history(limit=max(1, min(200, int(limit))), kind=(kind or None))

            with_entries = (
                bool(self._runtime_config.get("experiment.explain.include_raw_entries", True))
                if include_entries is None
                else bool(include_entries)
            )

            all_source_ids: set[int] = set()
            for row in rows:
                evidence_ids = [x for x in row.get("evidence", []) if isinstance(x, str) and x.startswith("ev_")]
                if not evidence_ids:
                    row["evidence_events"] = []
                    row["trigger_summary"] = {"events": 0, "source_entries": 0}
                    continue

                events = self.memory.get_events(evidence_ids[:24])
                event_items: List[Dict[str, Any]] = []
                for e in events:
                    item = {
                        "id": e.id,
                        "summary": e.summary,
                        "salience": e.salience,
                        "stood_firm": e.stood_firm,
                        "source_ids": list(e.source_ids),
                        "questions": list(e.questions[:6]),
                        "entities": list(e.entities[:6]),
                    }
                    event_items.append(item)
                    if with_entries:
                        all_source_ids.update(int(i) for i in e.source_ids)

                row["evidence_events"] = event_items
                row["trigger_summary"] = {
                    "events": len(event_items),
                    "source_entries": 0,
                }

            entry_map: Dict[int, Dict[str, Any]] = {}
            if with_entries and all_source_ids:
                for ent in self.journal.entries_by_ids(sorted(all_source_ids)):
                    entry_map[int(ent.id)] = {
                        "id": int(ent.id),
                        "session": ent.session,
                        "turn": int(ent.turn),
                        "role": ent.role,
                        "content": ent.content,
                        "wrote_at": float(ent.wrote_at),
                    }

            if with_entries and entry_map:
                for row in rows:
                    total_entries = 0
                    for item in row.get("evidence_events", []):
                        if not isinstance(item, dict):
                            continue
                        src_ids = [int(x) for x in item.get("source_ids", []) if int(x) in entry_map]
                        src_entries = [entry_map[i] for i in src_ids]
                        item["source_entries"] = src_entries
                        total_entries += len(src_entries)
                    if isinstance(row.get("trigger_summary"), dict):
                        row["trigger_summary"]["source_entries"] = total_entries

            return {
                "character": self.character,
                "kind": kind or "all",
                "include_entries": with_entries,
                "items": rows,
            }

    # ------------------------------------------------------------ 输入

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """写入一批原始证据到 pending 队列。"""
        session = str(payload.get("session") or self.config.default_session)
        turns = _normalise_turns(payload)
        if not turns:
            raise ValueError("ingest 需要 turns/messages 或 (turn, role, content)")

        max_turns = int(self._runtime_config["ingest.max_turns_per_request"])
        max_chars = int(self._runtime_config["ingest.max_content_chars"])
        overflow_trimmed = 0
        if len(turns) > max_turns:
            overflow_trimmed = len(turns) - max_turns
            turns = turns[-max_turns:]
        turns = [_truncate_turn_content(t, max_chars) for t in turns]

        with self._lock:
            self._metric_inc("growth.ingest_requests", 1)
            if overflow_trimmed:
                self._metric_inc("growth.overflow_trimmed_turns", overflow_trimmed)

            seen_turns = sorted({int(t["turn"]) for t in turns})
            gaps: List[Dict[str, int]] = []
            for t in seen_turns:
                gap = self.journal.observe_turn(self.character, session, t)
                if gap:
                    gaps.append({"from": int(gap[0]), "to": int(gap[1])})

            filtered_turns, dropped = _prefilter_evidence(turns)
            if dropped:
                self._metric_inc("growth.dropped_lightweight", dropped)

            if filtered_turns:
                queued = self.adapters.pending.enqueue_pending_evidence(
                    self.character,
                    session,
                    filtered_turns,
                    client=str(payload.get("client")) if payload.get("client") else None,
                    model=str(payload.get("model")) if payload.get("model") else None,
                )
            else:
                qstats0 = self.adapters.jobs.queue_stats(self.character)
                queued = {
                    "added": 0,
                    "deduped": 0,
                    "pending_evidence": int(qstats0.get("pending_evidence", 0)),
                    "jobs_pending": int(qstats0.get("jobs_pending", 0)),
                    "jobs_processing": int(qstats0.get("jobs_processing", 0)),
                }

            queue_now: Dict[str, int] = {}
            # 可选同步模式：本次请求内先处理一轮队列
            if _coerce_bool(payload.get("sync"), default=False):
                sync_jobs = int(self._runtime_config["queue.max_sync_jobs"])
                if sync_jobs > 0:
                    queue_now = self.adapters.jobs.drain_ingest_jobs(self.character, max_jobs=sync_jobs)
                    self._metric_inc("growth.queue_jobs_done", int(queue_now.get("jobs_done_now") or 0))
                    self._metric_inc("growth.queue_jobs_failed", int(queue_now.get("jobs_failed_now") or 0))

            qstats = self.adapters.jobs.queue_stats(self.character)
            pending = self.digester.pending_count()
            open_gaps = self.journal.open_gaps(self.character)
            return {
                "character": self.character,
                "session": session,
                "added": int(queued.get("added") or 0),
                "deduped": int(queued.get("deduped") or 0),
                "dropped_lightweight": dropped,
                "overflow_trimmed_turns": overflow_trimmed,
                "turns": seen_turns,
                "gaps": gaps,
                "open_gaps": open_gaps,
                "pending": pending,
                "pending_evidence": int(qstats.get("pending_evidence", 0)),
                "queue": qstats,
                "queue_now": queue_now,
                "alerts": self._build_alerts(qstats, pending, len(open_gaps)),
            }

    # ------------------------------------------------------------ 处理

    def digest_once(self, limit: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            self._metric_inc("growth.digest_requests", 1)
            max_limit = int(self._runtime_config["digest.max_limit"])
            safe_limit = max_limit if limit is None else max(1, min(int(limit), max_limit))

            queue_now = self.adapters.jobs.drain_ingest_jobs(
                self.character,
                max_jobs=int(self._runtime_config["queue.max_drain_jobs"]),
            )
            self._metric_inc("growth.queue_jobs_done", int(queue_now.get("jobs_done_now") or 0))
            self._metric_inc("growth.queue_jobs_failed", int(queue_now.get("jobs_failed_now") or 0))

            report = self.digester.digest_once(limit=safe_limit)
            out = report.as_dict()
            pending = self.digester.pending_count()
            qstats = self.adapters.jobs.queue_stats(self.character)
            open_gaps = len(self.journal.open_gaps(self.character))
            out["pending"] = pending
            out["queue"] = qstats
            out["queue_now"] = queue_now
            out["alerts"] = self._build_alerts(qstats, pending, open_gaps)
            out["limit"] = safe_limit
            out["decay"] = self._maybe_apply_decay_unlocked(force=False)
            return out

    def drain(self, max_rounds: int = 50) -> Dict[str, Any]:
        with self._lock:
            self._metric_inc("growth.drain_requests", 1)
            safe_rounds = max(1, min(int(max_rounds), int(self._runtime_config["drain.max_rounds"])))
            queue_now = self.adapters.jobs.drain_ingest_jobs(
                self.character,
                max_jobs=min(safe_rounds, int(self._runtime_config["queue.max_drain_jobs"])),
            )
            self._metric_inc("growth.queue_jobs_done", int(queue_now.get("jobs_done_now") or 0))
            self._metric_inc("growth.queue_jobs_failed", int(queue_now.get("jobs_failed_now") or 0))
            reports = self.grower.drain(max_rounds=safe_rounds)
            pending = self.digester.pending_count()
            qstats = self.adapters.jobs.queue_stats(self.character)
            open_gaps = len(self.journal.open_gaps(self.character))
            return {
                "rounds": len(reports),
                "max_rounds": safe_rounds,
                "reports": [r.as_dict() for r in reports],
                "pending": pending,
                "queue": qstats,
                "queue_now": queue_now,
                "alerts": self._build_alerts(qstats, pending, open_gaps),
                "decay": self._maybe_apply_decay_unlocked(force=False),
            }

    # ------------------------------------------------------------ 输出

    def build_context(self, query: str, learn: bool = False, sync_grow: bool = False) -> Dict[str, Any]:
        with self._lock:
            self._maybe_apply_decay_unlocked(force=False)
            # 对话链路指标与成长链路拆分统计。
            self._metric_inc("dialog.context_requests", 1)
            if learn:
                self._metric_inc("dialog.context_learn_requests", 1)
            sync_report = None
            if sync_grow:
                self._metric_inc("dialog.context_sync_grow", 1)
                try:
                    sync_report = self.digest_once(limit=20)
                except Exception:
                    pass
            pack = self.context.build(self.character, query=query, learn=learn)
            result = {"context": pack.as_dict(), "text": pack.render()}
            if sync_report is not None:
                result["sync_grow"] = {
                    "entries": sync_report.get("entries", 0),
                    "events": sync_report.get("events", 0),
                    "traits_touched": sync_report.get("traits_touched", 0),
                }
            return result

    def override_constants(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Hot-override constants in memory. Reset on restart."""
        import loam.core.constants as C
        if not hasattr(self, '_runtime_const_overrides'):
            self._runtime_const_overrides = {}
        applied = {}
        rejected = {}
        for name, val in overrides.items():
            if not name.isupper() or name.startswith('_'):
                rejected[name] = "invalid name"
                continue
            if not hasattr(C, name):
                rejected[name] = "not found"
                continue
            orig = getattr(C, name)
            if not isinstance(orig, type(val)):
                rejected[name] = f"type mismatch: {type(orig).__name__} vs {type(val).__name__}"
                continue
            setattr(C, name, val)
            self._runtime_const_overrides[name] = {"original": orig, "override": val}
            applied[name] = {"from": orig, "to": val}
        return {"applied": applied, "rejected": rejected, "total_overrides": len(self._runtime_const_overrides)}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "character": self.character,
                "root": str(self.root),
                "journal": self.journal.stats(self.character),
                "memory": self.memory.stats(),
                "pending": self.digester.pending_count(),
                "grower_alive": self.grower.alive,
                "last_error": self.grower.last_error,
            }

    def healthz(self) -> Dict[str, Any]:
        with self._lock:
            pending = self.digester.pending_count()
            ok = True
            if self.config.auto_start_grower and not self.grower.alive:
                ok = False
            return {
                "ok": ok,
                "character": self.character,
                "pending": pending,
                "open_gaps": len(self.journal.open_gaps(self.character)),
                "grower_alive": self.grower.alive,
                "last_error": self.grower.last_error,
                "ts": time.time(),
            }

    # ------------------------------------------------------------ grower

    def start_grower(self) -> Dict[str, Any]:
        self.grower.start()
        return {"grower_alive": self.grower.alive}

    def stop_grower(self) -> Dict[str, Any]:
        self.grower.stop()
        return {"grower_alive": self.grower.alive}

    # ------------------------------------------------------------ 生命周期

    def close(self) -> None:
        self.grower.stop()
        self.journal.close()
        self.memory.close()


class LoamHTTPServer(ThreadingHTTPServer):
    """把 service 挂在 server 上，handler 里直接拿。"""

    def __init__(self, server_address: tuple[str, int], service: LoamService):
        self.service = service
        super().__init__(server_address, LoamHandler)


class LoamHandler(BaseHTTPRequestHandler):
    server: LoamHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._send_json(200, {"ok": True, "character": self.server.service.character})
                return

            if not self._require_auth(path):
                return

            if path == "/healthz":
                self._send_json(200, self.server.service.healthz())
                return

            if path == "/stats":
                self._send_json(200, self.server.service.stats())
                return

            if path == "/dashboard":
                self._send_json(200, self.server.service.dashboard())
                return

            if path == "/config":
                self._send_json(200, self.server.service.runtime_config())
                return

            if path == "/recompute/history":
                limit_text = (qs.get("limit") or ["20"])[0]
                self._send_json(200, self.server.service.recompute_history(limit=int(limit_text or 20)))
                return

            if path == "/experiments":
                limit_text = (qs.get("limit") or ["20"])[0]
                self._send_json(200, self.server.service.experiment_history(limit=int(limit_text or 20)))
                return

            if path == "/experiments/flags":
                self._send_json(200, self.server.service.experiment_flags())
                return

            if path == "/explain":
                kind = (qs.get("kind") or [""])[0]
                limit_text = (qs.get("limit") or ["20"])[0]
                include_raw = (qs.get("include_entries") or [None])[0]
                include_entries = None if include_raw is None else _coerce_bool(include_raw, default=False)
                self._send_json(
                    200,
                    self.server.service.explain(
                        kind=kind,
                        limit=int(limit_text or 20),
                        include_entries=include_entries,
                    ),
                )
                return

            if path == "/context":
                query = (qs.get("q") or [""])[0]
                learn = _coerce_bool((qs.get("learn") or [None])[0], default=False)
                sync_grow = _coerce_bool((qs.get("sync_grow") or [None])[0], default=False)
                self._send_json(200, self.server.service.build_context(query, learn=learn, sync_grow=sync_grow))
                return

            if path == "/narrative":
                self._send_json(200, self.server.service.narrative())
                return
            if path == "/network" or path.startswith("/network?"):
                net = self.server.service.memory.load_network()
                limit = int((qs.get("limit") or ["80"])[0])
                nodes = []
                edges = []
                for nid, ndata in net.nodes.items():
                    d = ndata if isinstance(ndata, dict) else getattr(ndata, '__dict__', {})
                    nodes.append({
                        "id": nid,
                        "weight": round(float(d.get("weight", 0)), 4),
                        "degree": int(d.get("degree", 0)),
                    })
                for (src, dst), edata in net.edges.items():
                    w = float(edata) if isinstance(edata, (int, float)) else float(getattr(edata, 'weight', 0))
                    edges.append({"source": src, "target": dst, "weight": round(w, 4)})
                nodes.sort(key=lambda x: x["weight"], reverse=True)
                nodes = nodes[:limit]
                edges.sort(key=lambda x: x["weight"], reverse=True)
                edges = edges[:limit * 2]
                self._send_json(200, {
                    "nodes": nodes,
                    "edges": edges,
                    "total_nodes": len(net.nodes),
                    "total_edges": len(net.edges),
                })
                return
            if path == "/constants" or path.startswith("/constants?"):
                import loam.core.constants as C
                all_consts = {}
                for name in dir(C):
                    if name.isupper() and not name.startswith('_'):
                        val = getattr(C, name)
                        if isinstance(val, (int, float, bool, str)):
                            all_consts[name] = val
                overrides = self.server.service._runtime_const_overrides if hasattr(self.server.service, '_runtime_const_overrides') else {}
                self._send_json(200, {"constants": all_consts, "overrides": overrides})
                return
            self._send_json(404, {"error": f"unknown route: {path}"})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_internal_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if not self._require_auth(path):
                return

            payload = self._read_json()

            if path == "/ingest":
                self._send_json(200, self.server.service.ingest(payload))
                return

            if path == "/digest":
                limit = payload.get("limit")
                self._send_json(200, self.server.service.digest_once(limit=int(limit) if limit else None))
                return

            if path == "/drain":
                rounds = int(payload.get("max_rounds") or 50)
                self._send_json(200, self.server.service.drain(max_rounds=rounds))
                return

            if path == "/context":
                query = str(payload.get("query") or "")
                learn = _coerce_bool(payload.get("learn"), default=False)
                sync_grow = _coerce_bool(payload.get("sync_grow"), default=False)
                self._send_json(200, self.server.service.build_context(query, learn=learn, sync_grow=sync_grow))
                return

            if path == "/constants":
                overrides = payload.get("overrides") or {}
                if not isinstance(overrides, dict):
                    raise ValueError("overrides must be a dict")
                result = self.server.service.override_constants(overrides)
                self._send_json(200, result)
                return
            if path == "/grower/start":
                self._send_json(200, self.server.service.start_grower())
                return

            if path == "/grower/stop":
                self._send_json(200, self.server.service.stop_grower())
                return

            if path == "/config/update":
                updates = payload.get("updates")
                if not isinstance(updates, dict):
                    raise ValueError("updates 必须是对象")
                note = str(payload.get("note") or "")
                self._send_json(200, self.server.service.update_runtime_config(updates, note=note))
                return

            if path == "/config/rollback":
                version = payload.get("version")
                if version is None:
                    raise ValueError("rollback 需要 version")
                note = str(payload.get("note") or "")
                self._send_json(200, self.server.service.rollback_runtime_config(int(version), note=note))
                return

            if path in ("/experiments/update", "/experiments/flags/update"):
                flags = payload.get("flags")
                if not isinstance(flags, dict):
                    raise ValueError("flags 必须是对象")
                note = str(payload.get("note") or "")
                merge = _coerce_bool(payload.get("merge"), default=True)
                self._send_json(200, self.server.service.update_experiment_flags(flags, note=note, merge=merge))
                return

            if path == "/recompute":
                mode = str(payload.get("mode") or "incremental")
                rounds = payload.get("max_rounds")
                note = str(payload.get("note") or "")
                self._send_json(
                    200,
                    self.server.service.recompute(
                        mode=mode,
                        max_rounds=int(rounds) if rounds is not None else None,
                        note=note,
                    ),
                )
                return

            self._send_json(404, {"error": f"unknown route: {path}"})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_internal_error(exc)

    # ------------------------------------------------------------ 工具

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b"{}"
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid json: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body 必须是对象")
        return data

    def _require_auth(self, path: str) -> bool:
        expected = self.server.service.api_key
        if not expected:
            return True

        # 健康探针默认放行，避免部署平台被鉴权卡死。
        if path in ("/health", "/healthz"):
            return True

        presented = (self.headers.get("X-API-Key") or "").strip()
        if not presented:
            auth = (self.headers.get("Authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                presented = auth[7:].strip()

        if presented == expected:
            return True

        self._send_json(401, {"error": "unauthorized", "message": "missing or invalid api key"})
        return False

    def _send_internal_error(self, exc: Exception) -> None:
        rid = uuid.uuid4().hex[:12]
        trace = traceback.format_exc()
        print(
            f"[loam][error][{rid}] {type(exc).__name__}: {exc}\n{trace}",
            file=sys.stderr,
            flush=True,
        )
        self._send_json(500, {"error": "internal_error", "request_id": rid})

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # 测试里尽量安静。需要时可改成 print。
        return


def build_server(service: LoamService, host: str = "127.0.0.1", port: int = 8765) -> LoamHTTPServer:
    return LoamHTTPServer((host, port), service)


def run_server(service: LoamService, host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = build_server(service, host=host, port=port)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        service.close()


def _normalise_turns(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把输入统一成 Journal.append_batch 需要的结构。"""
    if isinstance(payload.get("turns"), list):
        turns = payload["turns"]
        return [_one_turn(x) for x in turns if isinstance(x, dict)]

    if isinstance(payload.get("messages"), list):
        base_turn = int(payload.get("turn") or 1)
        turns: List[Dict[str, Any]] = []
        for i, msg in enumerate(payload["messages"]):
            if not isinstance(msg, dict):
                continue
            t = dict(msg)
            t.setdefault("turn", base_turn + i)
            turns.append(_one_turn(t))
        return turns

    if all(k in payload for k in ("turn", "role", "content")):
        return [_one_turn(payload)]

    return []


def _one_turn(raw: Dict[str, Any]) -> Dict[str, Any]:
    turn = int(raw.get("turn"))
    role = str(raw.get("role") or "").strip()
    content = str(raw.get("content") or "").strip()
    if not role or not content:
        raise ValueError("每条 turn 都需要 role 和 content")

    out: Dict[str, Any] = {
        "turn": turn,
        "role": role,
        "content": content,
    }

    if "wrote_at" in raw:
        out["wrote_at"] = float(raw["wrote_at"])
    if "meta" in raw and isinstance(raw["meta"], dict):
        out["meta"] = raw["meta"]
    return out


_LIGHTWEIGHT_REPLIES = {
    "嗯",
    "好的",
    "好",
    "收到",
    "知道了",
    "明白",
    "明白了",
    "ok",
    "okay",
    "got it",
    "roger",
}

_SMALL_TALK_PHRASES = {
    "你好",
    "您好",
    "嗨",
    "hi",
    "hello",
    "在吗",
    "在不在",
    "早上好",
    "晚上好",
    "午安",
}

_FILLER_WORDS = {
    "嗯",
    "呃",
    "额",
    "啊",
    "哦",
    "唉",
    "哈",
    "哈哈",
    "哈哈哈",
    "…",
    "...",
    "？",
    "?",
    "！",
    "!",
}

_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)


def _prefilter_evidence(turns: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    """轻量预过滤：过滤寒暄/语气词/重复，减少低价值证据进入成长链路。"""
    kept: List[Dict[str, Any]] = []
    dropped = 0
    seen: set[str] = set()

    for t in turns:
        role = str(t.get("role") or "").strip().lower()
        content = str(t.get("content") or "")
        normalized = " ".join(content.strip().split())
        low = normalized.lower()

        if not normalized:
            dropped += 1
            continue

        # 同批重复内容直接去掉，避免无效放大。
        signature = f"{role}\x00{low}"
        if signature in seen:
            dropped += 1
            continue

        if _is_lightweight_noise(role, normalized, low):
            dropped += 1
            continue

        seen.add(signature)
        item = dict(t)
        item["content"] = normalized
        kept.append(item)

    return kept, dropped


def _is_lightweight_noise(role: str, normalized: str, low: str) -> bool:
    if _PUNCT_ONLY_RE.match(normalized):
        return True

    if low in _SMALL_TALK_PHRASES:
        return True

    if role == "assistant" and low in _LIGHTWEIGHT_REPLIES:
        return True

    if role == "assistant" and low in _FILLER_WORDS:
        return True

    if role in ("assistant", "system") and len(normalized) <= 2 and low not in {"不", "行"}:
        return True

    if role == "user" and low in _FILLER_WORDS and len(normalized) <= 3:
        return True

    return False


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return int(default)


def _clamp_int(value: Any, default: int, lower: int, upper: int) -> int:
    out = _safe_int(value, default)
    if out < lower:
        return int(lower)
    if out > upper:
        return int(upper)
    return int(out)


def _clamp_float(value: Any, default: float, lower: float, upper: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        out = float(default)
    if out < lower:
        return float(lower)
    if out > upper:
        return float(upper)
    return float(out)


def _truncate_turn_content(turn: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    """限制单条输入长度，避免超长内容挤爆预算。"""
    text = str(turn.get("content") or "")
    if len(text) <= max_chars:
        return turn
    out = dict(turn)
    out["content"] = text[:max_chars].rstrip() + "…"
    return out
