"""存储抽象层（Adapter）。

目标：把 Journal/Pending/Job/Trait/Config 的访问面显式拆开，
后续切换 Postgres/TiKV 时只替换 Adapter，不改上层业务流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Sequence

from loam.core.growth import Trait

from .journal import Entry, Journal
from .memory import Event, Memory


class PendingAdapter(Protocol):
    def enqueue_pending_evidence(
        self,
        character: str,
        session: str,
        turns: Sequence[Dict[str, object]],
        client: str | None = None,
        model: str | None = None,
    ) -> Dict[str, int]: ...

    def pending_evidence_count(self, character: str) -> int: ...


class JobAdapter(Protocol):
    def drain_ingest_jobs(self, character: str, max_jobs: int = 8) -> Dict[str, int]: ...

    def queue_stats(self, character: str) -> Dict[str, int]: ...

    def queue_sessions(self, character: str, limit: int = 20) -> List[Dict[str, object]]: ...

    def recent_ingest_jobs(self, character: str, limit: int = 20) -> List[Dict[str, object]]: ...


class TraitAdapter(Protocol):
    def load_traits(self, include_retired: bool = False) -> List[Trait]: ...

    def save_trait(self, trait: Trait, from_seed: bool = False) -> None: ...

    def save_traits(self, traits: Sequence[Trait]) -> None: ...

    def retire_trait(self, trait_id: str) -> None: ...


class ConfigAdapter(Protocol):
    def runtime_config(self) -> Dict[str, object]: ...

    def set_runtime_config(
        self,
        config: Dict[str, object],
        note: str = "",
        actor: str = "system",
    ) -> int: ...

    def runtime_config_history(self, limit: int = 20) -> List[Dict[str, object]]: ...

    def rollback_runtime_config(
        self,
        version_id: int,
        note: str = "",
        actor: str = "rollback",
    ) -> Dict[str, object]: ...

    def experiment_flags(self) -> Dict[str, object]: ...

    def set_experiment_flags(
        self,
        flags: Dict[str, object],
        note: str = "",
        actor: str = "system",
        merge: bool = True,
    ) -> Dict[str, object]: ...

    def experiment_history(self, limit: int = 20) -> List[Dict[str, object]]: ...


@dataclass
class SQLitePendingAdapter:
    journal: Journal

    def enqueue_pending_evidence(
        self,
        character: str,
        session: str,
        turns: Sequence[Dict[str, object]],
        client: str | None = None,
        model: str | None = None,
    ) -> Dict[str, int]:
        return self.journal.enqueue_pending_evidence(
            character,
            session,
            turns,
            client=client,
            model=model,
        )

    def pending_evidence_count(self, character: str) -> int:
        return self.journal.pending_evidence_count(character)


@dataclass
class SQLiteJobAdapter:
    journal: Journal

    def drain_ingest_jobs(self, character: str, max_jobs: int = 8) -> Dict[str, int]:
        return self.journal.drain_ingest_jobs(character, max_jobs=max_jobs)

    def queue_stats(self, character: str) -> Dict[str, int]:
        return self.journal.queue_stats(character)

    def queue_sessions(self, character: str, limit: int = 20) -> List[Dict[str, object]]:
        return self.journal.queue_sessions(character, limit=limit)

    def recent_ingest_jobs(self, character: str, limit: int = 20) -> List[Dict[str, object]]:
        return self.journal.recent_ingest_jobs(character, limit=limit)


@dataclass
class SQLiteTraitAdapter:
    memory: Memory

    def load_traits(self, include_retired: bool = False) -> List[Trait]:
        return self.memory.load_traits(include_retired=include_retired)

    def save_trait(self, trait: Trait, from_seed: bool = False) -> None:
        self.memory.save_trait(trait, from_seed=from_seed)

    def save_traits(self, traits: Sequence[Trait]) -> None:
        self.memory.save_traits(traits)

    def retire_trait(self, trait_id: str) -> None:
        self.memory.retire_trait(trait_id)


@dataclass
class SQLiteConfigAdapter:
    memory: Memory

    def runtime_config(self) -> Dict[str, object]:
        return self.memory.runtime_config()

    def set_runtime_config(
        self,
        config: Dict[str, object],
        note: str = "",
        actor: str = "system",
    ) -> int:
        return self.memory.set_runtime_config(config, note=note, actor=actor)

    def runtime_config_history(self, limit: int = 20) -> List[Dict[str, object]]:
        return self.memory.runtime_config_history(limit=limit)

    def rollback_runtime_config(
        self,
        version_id: int,
        note: str = "",
        actor: str = "rollback",
    ) -> Dict[str, object]:
        return self.memory.rollback_runtime_config(version_id, note=note, actor=actor)

    def experiment_flags(self) -> Dict[str, object]:
        return self.memory.experiment_flags()

    def set_experiment_flags(
        self,
        flags: Dict[str, object],
        note: str = "",
        actor: str = "system",
        merge: bool = True,
    ) -> Dict[str, object]:
        return self.memory.set_experiment_flags(flags, note=note, actor=actor, merge=merge)

    def experiment_history(self, limit: int = 20) -> List[Dict[str, object]]:
        return self.memory.experiment_history(limit=limit)


@dataclass
class SQLiteStorageAdapters:
    """SQLite 默认实现：上层依赖 Adapter 面，不直接依赖底层实现细节。"""

    journal: Journal
    memory: Memory
    pending: SQLitePendingAdapter
    jobs: SQLiteJobAdapter
    traits: SQLiteTraitAdapter
    config: SQLiteConfigAdapter

    @classmethod
    def from_instances(cls, journal: Journal, memory: Memory) -> "SQLiteStorageAdapters":
        return cls(
            journal=journal,
            memory=memory,
            pending=SQLitePendingAdapter(journal),
            jobs=SQLiteJobAdapter(journal),
            traits=SQLiteTraitAdapter(memory),
            config=SQLiteConfigAdapter(memory),
        )

    # 预留：供迁移脚本/适配层做能力探针。
    def capabilities(self) -> Dict[str, Any]:
        return {
            "backend": "sqlite",
            "supports_transactions": True,
            "supports_fts": True,
            "adapters": ["pending", "jobs", "traits", "config"],
        }
