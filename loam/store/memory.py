"""熟料 —— 事件、连线、特质、自我，以及每一次变化的账。

日记是生的，这里是煮过的。两者分开的理由：煮要调模型、会失败、
可能需要重做；料必须先保住。所以这个库里的一切都是可以从
journal 重新推导出来的派生物 —— 坏了就重建。

存四样东西：

events    情景记忆。每条带显著性、情绪、以及"这条能回答什么问题"。
          最后那个字段是跨过"因果距离"的关键 —— 检索时用当前的话
          去跟这些问题比，而不是跟原文比。
edges     赫布连线。网络的形状，也就是人格实际起作用的地方。
traits    一条条"我觉得"，含强度、蓄水池、来历。
identity  自述、常驻档案卡，以及 changelog。

changelog 是这个项目最有说服力的东西：半年以后你能翻出来看，
它是在哪一天、因为哪几件事，变成现在这个样子的。
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loam.core.growth import Trait
from loam.core.network import Network

SCHEMA = """
-- ---------------------------------------------------------------- 情景记忆
CREATE TABLE IF NOT EXISTS events (
    id          TEXT    PRIMARY KEY,
    summary     TEXT    NOT NULL,
    -- 指回原始日记。任何事件都必须有来历。
    source_ids  TEXT    NOT NULL,
    session     TEXT,
    salience    REAL    NOT NULL DEFAULT 0.5,
    -- 情绪效价 [-1, 1]。负为难受，正为愉快。
    valence     REAL    NOT NULL DEFAULT 0.0,
    -- 这条记忆能回答哪些问题。检索时拿当前的话来跟它们比，
    -- 而不是跟 summary 比 —— 这样"我明天有点紧张"就能命中
    -- "他为什么怕开会"，因果距离一下就被跨过去了。
    questions   TEXT    NOT NULL DEFAULT '[]',
    -- 参与的人、涉及的实体，用于关键词命中（专有名词语义相似救不了）
    entities    TEXT    NOT NULL DEFAULT '[]',
    -- 这条是不是"它顶住了我"的时刻。身份权重最高的一类。
    stood_firm  INTEGER NOT NULL DEFAULT 0,
    happened_at REAL    NOT NULL,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_time ON events(happened_at);
CREATE INDEX IF NOT EXISTS idx_events_salience ON events(salience DESC);
CREATE INDEX IF NOT EXISTS idx_events_firm ON events(stood_firm);

-- 全文索引。关键词命中是语义检索救不了的那一半：
-- 人名、地名、专有名词，意思相近毫无用处，必须字面命中。
--
-- 不用 external content + 触发器，因为索引里存的不是原文，是切好的词：
-- SQLite 自带的分词器（unicode61）把连续的汉字当成一个整词
-- （"上次汇报被领导打断" 是一个 token），中文因此完全搜不出来。
-- 又不能依赖需要编译的分词扩展 —— Termux 上装不上。
-- 所以自己切：中文切二元词，西文照原样，切完拿空格连起来喂给 fts5。
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    event_id UNINDEXED, body,
    tokenize='unicode61'
);

-- ---------------------------------------------------------------- 网络
CREATE TABLE IF NOT EXISTS nodes (
    id                TEXT PRIMARY KEY,
    salience          REAL    NOT NULL DEFAULT 0.5,
    anchor            INTEGER NOT NULL DEFAULT 0,
    created_cycle     INTEGER NOT NULL DEFAULT 0,
    last_active_cycle INTEGER NOT NULL DEFAULT 0,
    activations       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    a      TEXT NOT NULL,
    b      TEXT NOT NULL,
    weight REAL NOT NULL,
    PRIMARY KEY (a, b)
);

-- ---------------------------------------------------------------- 特质
CREATE TABLE IF NOT EXISTS traits (
    id             TEXT PRIMARY KEY,
    text           TEXT    NOT NULL,
    strength       REAL    NOT NULL DEFAULT 0.0,
    pending        REAL    NOT NULL DEFAULT 0.0,
    -- 动态门槛等级：每次发生质变后递增。
    gate_level     INTEGER NOT NULL DEFAULT 0,
    -- 快态与惯性：允许心电图式波动，但不覆盖长期稳态。
    transient      REAL    NOT NULL DEFAULT 0.0,
    momentum       REAL    NOT NULL DEFAULT 0.0,
    -- 生命周期：静默多久、是否还在暖启动。
    inactive_cycles  INTEGER NOT NULL DEFAULT 0,
    warmup_remaining INTEGER NOT NULL DEFAULT 0,
    -- 已提交的来历
    evidence       TEXT    NOT NULL DEFAULT '[]',
    -- 蓄水池里攒着但还没质变的来历。不能丢。
    staged         TEXT    NOT NULL DEFAULT '[]',
    -- 低置信/高歧义、尚未被独立印证的证据池。
    uncertain      TEXT    NOT NULL DEFAULT '[]',
    reinforced     INTEGER NOT NULL DEFAULT 0,
    contradicted   INTEGER NOT NULL DEFAULT 0,
    expressed      INTEGER NOT NULL DEFAULT 0,
    opportunities  INTEGER NOT NULL DEFAULT 0,
    formed_at      TEXT,
    last_commit_at TEXT,
    -- 来自角色卡的种子特质。土壤，全程保留。
    from_seed      INTEGER NOT NULL DEFAULT 0,
    -- 运行期调节项：有界随机、置信闸门、蛰伏阈值。
    fuzziness        REAL    NOT NULL DEFAULT 0.0,
    uncertainty_gate REAL    NOT NULL DEFAULT 0.55,
    dormancy_after   INTEGER NOT NULL DEFAULT 24,
    retired        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_traits_strength ON traits(retired, strength DESC);

-- ---------------------------------------------------------------- 自我
-- 自述的每一版都留着，而且记下它是从哪些记忆推出来的。
-- 关键：重写时输入是 journal + traits，绝不是上一版自述。
CREATE TABLE IF NOT EXISTS narratives (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    -- 'derived' 从记忆推导 | 'rebuilt' 从零重建（漂移检测用）
    kind        TEXT    NOT NULL DEFAULT 'derived',
    basis       TEXT    NOT NULL DEFAULT '[]',
    cycle       INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);

-- 常驻档案卡。永远在线，不走检索。
CREATE TABLE IF NOT EXISTS dossier (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    -- 被新信息替代时不删，只标记。"他变了"本身就是重要信息。
    superseded_by TEXT,
    source_ids  TEXT NOT NULL DEFAULT '[]',
    confidence  REAL NOT NULL DEFAULT 0.8,
    updated_at  REAL NOT NULL
);

-- ---------------------------------------------------------------- 账
-- 人格的每一次变化都记一笔。可审计、可回溯。
CREATE TABLE IF NOT EXISTS changelog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle       INTEGER NOT NULL,
    kind        TEXT    NOT NULL,
    target      TEXT,
    before      TEXT,
    after       TEXT,
    reason      TEXT    NOT NULL,
    -- 依据哪几件事。空的一律拒绝写入。
    evidence    TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_changelog_cycle ON changelog(cycle);

-- ---------------------------------------------------------------- 状态
CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 运行时参数版本。只回滚配置，不改历史真值。
CREATE TABLE IF NOT EXISTS config_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT    NOT NULL DEFAULT 'system',
    note        TEXT    NOT NULL DEFAULT '',
    config_json TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_config_versions_created
    ON config_versions(created_at DESC);

-- 派生权重衰减：不删原始真值，只衰减可回放层的权重。
CREATE TABLE IF NOT EXISTS event_decay (
    event_id      TEXT PRIMARY KEY,
    base_salience REAL NOT NULL,
    decay_weight  REAL NOT NULL DEFAULT 1.0,
    updated_at    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_decay_weight
    ON event_decay(decay_weight);

-- 参数实验开关与审计。
CREATE TABLE IF NOT EXISTS experiment_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT    NOT NULL DEFAULT 'system',
    note        TEXT    NOT NULL DEFAULT '',
    flags_json  TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_audit_created
    ON experiment_audit(created_at DESC);

-- 重算任务审计（增量 / 全量）。
CREATE TABLE IF NOT EXISTS recompute_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    mode         TEXT    NOT NULL,
    trigger      TEXT    NOT NULL DEFAULT 'api',
    status       TEXT    NOT NULL,
    from_cycle   INTEGER NOT NULL DEFAULT 0,
    to_cycle     INTEGER NOT NULL DEFAULT 0,
    details_json TEXT    NOT NULL DEFAULT '{}',
    created_at   REAL    NOT NULL,
    finished_at  REAL
);

CREATE INDEX IF NOT EXISTS idx_recompute_runs_created
    ON recompute_runs(created_at DESC);
"""
#: FTS 索引由 add_event 显式维护，不用触发器 —— 入索引前要先在
#: Python 里分词，SQL 里做不到。
TRIGGERS: List[str] = []



@dataclass
class Event:
    """一条情景记忆。"""

    id: str
    summary: str
    source_ids: List[int]
    session: Optional[str] = None
    salience: float = 0.5
    valence: float = 0.0
    questions: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    stood_firm: bool = False
    happened_at: float = 0.0
    created_at: float = 0.0

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.happened_at))


class Memory:
    """熟料库。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)
        self._ensure_schema_compat()
        for trig in TRIGGERS:
            self._db.execute(trig)
        self._db.commit()

    def _ensure_schema_compat(self) -> None:
        """向后兼容旧库：按需补齐新字段。"""
        trait_columns = [
            ("gate_level", "gate_level INTEGER NOT NULL DEFAULT 0"),
            ("transient", "transient REAL NOT NULL DEFAULT 0.0"),
            ("momentum", "momentum REAL NOT NULL DEFAULT 0.0"),
            ("inactive_cycles", "inactive_cycles INTEGER NOT NULL DEFAULT 0"),
            ("warmup_remaining", "warmup_remaining INTEGER NOT NULL DEFAULT 0"),
            ("uncertain", "uncertain TEXT NOT NULL DEFAULT '[]'"),
            ("fuzziness", "fuzziness REAL NOT NULL DEFAULT 0.0"),
            ("uncertainty_gate", "uncertainty_gate REAL NOT NULL DEFAULT 0.55"),
            ("dormancy_after", "dormancy_after INTEGER NOT NULL DEFAULT 24"),
            ("from_seed", "from_seed INTEGER NOT NULL DEFAULT 0"),
        ]
        for col, ddl in trait_columns:
            self._ensure_column("traits", col, ddl)

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cols = {
            str(r["name"])
            for r in self._db.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in cols:
            return
        self._db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    # ------------------------------------------------------------ 事件
    def add_event(self, event: Event) -> None:
        """写入一条情景记忆。必须有来历。"""
        if not event.source_ids:
            raise ValueError("事件必须指回原始日记（source_ids 不可为空）")
        now = time.time()
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO events"
                " (id, summary, source_ids, session, salience, valence,"
                "  questions, entities, stood_firm, happened_at, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.id,
                    event.summary,
                    json.dumps(event.source_ids),
                    event.session,
                    event.salience,
                    event.valence,
                    json.dumps(event.questions, ensure_ascii=False),
                    json.dumps(event.entities, ensure_ascii=False),
                    int(event.stood_firm),
                    event.happened_at or now,
                    event.created_at or now,
                ),
            )
            # 派生权重层：保留 base_salience，后续只衰减 decay_weight。
            self._db.execute(
                "INSERT INTO event_decay (event_id, base_salience, decay_weight, updated_at)"
                " VALUES (?,?,?,?)"
                " ON CONFLICT(event_id) DO UPDATE SET"
                "   base_salience=excluded.base_salience,"
                "   decay_weight=CASE"
                "       WHEN event_decay.decay_weight <= 0 THEN 1.0"
                "       ELSE event_decay.decay_weight"
                "   END,"
                "   updated_at=excluded.updated_at",
                (event.id, float(event.salience), 1.0, now),
            )
        self._index_event(event)


    def _index_event(self, event: Event) -> None:
        """把一条事件切好词塞进 FTS。已有的先删掉，避免重煮后留下旧词。"""
        body = _segment(
            " ".join([event.summary] + event.questions + event.entities)
        )
        with self._db:
            self._db.execute("DELETE FROM events_fts WHERE event_id=?", (event.id,))
            self._db.execute(
                "INSERT INTO events_fts(event_id, body) VALUES (?,?)",
                (event.id, body),
            )

    def get_event(self, event_id: str) -> Optional[Event]:
        row = self._db.execute(
            "SELECT e.*,"
            " COALESCE(d.base_salience * d.decay_weight, e.salience) AS effective_salience"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
            " WHERE e.id=?",
            (event_id,),
        ).fetchone()
        return _to_event(row) if row else None

    def get_events(self, ids: Sequence[str]) -> List[Event]:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self._db.execute(
            "SELECT e.*,"
            " COALESCE(d.base_salience * d.decay_weight, e.salience) AS effective_salience"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
            f" WHERE e.id IN ({marks})",
            list(ids),
        ).fetchall()
        by_id = {r["id"]: _to_event(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """关键词检索。只负责找门口在哪 —— 进门之后走网络自己的路。

        同时搜 summary、questions 和 entities。questions 那一栏是
        为了跨越因果距离：你说"我明天有点紧张"，会命中某条记忆的
        "他为什么怕开会"。
        """
        terms = _fts_terms(query)
        if not terms:
            return []
        try:
            rows = self._db.execute(
                "SELECT event_id AS id, bm25(events_fts) AS score"
                " FROM events_fts"
                " WHERE events_fts MATCH ?"
                " ORDER BY score LIMIT ?",
                (terms, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        # bm25 越小越相关，翻成越大越相关
        return [(r["id"], -float(r["score"])) for r in rows]

    def reindex(self) -> int:
        """重建全文索引。分词规则改过之后要跑一次。"""
        with self._db:
            self._db.execute("DELETE FROM events_fts")
        n = 0
        for row in self._db.execute("SELECT * FROM events").fetchall():
            self._index_event(_to_event(row))
            n += 1
        return n


    def recent_events(self, limit: int = 50, session: Optional[str] = None) -> List[Event]:
        sql = (
            "SELECT e.*,"
            " COALESCE(d.base_salience * d.decay_weight, e.salience) AS effective_salience"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
        )
        args: List[object] = []
        if session:
            sql += " WHERE e.session=?"
            args.append(session)
        sql += " ORDER BY e.happened_at DESC LIMIT ?"
        args.append(limit)
        return [_to_event(r) for r in self._db.execute(sql, args).fetchall()]

    def stood_firm_events(self, limit: int = 20) -> List[Event]:
        """它顶住了我的那些时刻。

        这是它长出"我"的唯一训练信号。一个人的自我不是在被认同的
        时候确立的，是在压力下没让步的时候。所以单独开一个查询。
        """
        rows = self._db.execute(
            "SELECT e.*,"
            " COALESCE(d.base_salience * d.decay_weight, e.salience) AS effective_salience"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
            " WHERE e.stood_firm=1"
            " ORDER BY effective_salience DESC, e.happened_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_to_event(r) for r in rows]
    def update_salience(self, event_id: str, salience: float) -> None:
        """重估重要性。睡眠时做 —— 有些事当时不觉得，后来才知道重要。"""
        value = max(0.0, min(1.0, salience))
        with self._db:
            self._db.execute(
                "UPDATE events SET salience=? WHERE id=?",
                (value, event_id),
            )
            self._db.execute(
                "INSERT INTO event_decay (event_id, base_salience, decay_weight, updated_at)"
                " VALUES (?,?,?,?)"
                " ON CONFLICT(event_id) DO UPDATE SET"
                "   base_salience=excluded.base_salience,"
                "   updated_at=excluded.updated_at",
                (event_id, value, 1.0, time.time()),
            )

    def apply_event_decay(
        self,
        half_life_hours: float = 72.0,
        min_weight: float = 0.25,
        stood_firm_floor: float = 0.55,
        now: Optional[float] = None,
    ) -> Dict[str, float]:
        """按时间衰减事件权重。

        只改 event_decay 层，不改 events 里的原始 salience 真值。
        """
        ts = float(now if now is not None else time.time())
        half_life_hours = max(0.1, float(half_life_hours))
        min_weight = max(0.0, min(1.0, float(min_weight)))
        stood_firm_floor = max(min_weight, min(1.0, float(stood_firm_floor)))
        half_life_seconds = max(60.0, half_life_hours * 3600.0)

        rows = self._db.execute(
            "SELECT id, salience, happened_at, stood_firm FROM events"
        ).fetchall()

        updated = 0
        with self._db:
            for r in rows:
                age = max(0.0, ts - float(r["happened_at"] or ts))
                decay = pow(0.5, age / half_life_seconds)
                floor = stood_firm_floor if int(r["stood_firm"] or 0) else min_weight
                weight = max(floor, min(1.0, decay))
                self._db.execute(
                    "INSERT INTO event_decay (event_id, base_salience, decay_weight, updated_at)"
                    " VALUES (?,?,?,?)"
                    " ON CONFLICT(event_id) DO UPDATE SET"
                    "   base_salience=excluded.base_salience,"
                    "   decay_weight=excluded.decay_weight,"
                    "   updated_at=excluded.updated_at",
                    (r["id"], float(r["salience"]), float(weight), ts),
                )
                updated += 1

        return {
            "updated": float(updated),
            "half_life_hours": float(half_life_hours),
            "min_weight": float(min_weight),
            "stood_firm_floor": float(stood_firm_floor),
        }

    def event_window_stats(
        self,
        window_seconds: int = 86400,
        bucket_seconds: int = 3600,
        limit: int = 48,
        session: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, object]:
        """按时间窗聚合事件，给 dashboard 用。"""
        bucket = max(60, int(bucket_seconds))
        window = max(bucket, int(window_seconds))
        cap = max(1, min(int(limit), 512))
        ts = float(now if now is not None else time.time())
        since = ts - float(window)

        sql = (
            "SELECT CAST(e.happened_at / ? AS INTEGER) * ? AS bucket_start,"
            " COUNT(*) AS events,"
            " AVG(COALESCE(d.base_salience * d.decay_weight, e.salience)) AS avg_salience,"
            " SUM(e.stood_firm) AS stood_firm"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
            " WHERE e.happened_at>=?"
        )
        args: List[object] = [bucket, bucket, since]
        if session:
            sql += " AND e.session=?"
            args.append(session)
        sql += " GROUP BY bucket_start ORDER BY bucket_start DESC LIMIT ?"
        args.append(cap)

        rows = self._db.execute(sql, args).fetchall()
        points: List[Dict[str, object]] = []
        for r in reversed(rows):
            start = float(r["bucket_start"])
            points.append(
                {
                    "start": start,
                    "end": start + float(bucket),
                    "events": int(r["events"] or 0),
                    "stood_firm": int(r["stood_firm"] or 0),
                    "avg_salience": round(float(r["avg_salience"] or 0.0), 4),
                }
            )

        merged_points = _merge_sparse_points(points, bucket_seconds=bucket)
        return {
            "window_seconds": window,
            "bucket_seconds": bucket,
            "points": points,
            "merged_points": merged_points,
            "fragment_ratio": round((len(points) / max(1, len(merged_points))), 4),
        }

    # ------------------------------------------------------------ 网络


    def load_network(self) -> Network:
        nodes = [dict(r) for r in self._db.execute("SELECT * FROM nodes").fetchall()]
        edges = [
            [r["a"], r["b"], r["weight"]]
            for r in self._db.execute("SELECT * FROM edges").fetchall()
        ]
        cycle = int(self.get_state("cycle", "0"))
        for n in nodes:
            n["anchor"] = bool(n["anchor"])
        return Network.from_dict({"cycle": cycle, "nodes": nodes, "edges": edges})

    def save_network(self, net: Network) -> None:
        data = net.to_dict()
        with self._db:
            self._db.execute("DELETE FROM nodes")
            self._db.execute("DELETE FROM edges")
            self._db.executemany(
                "INSERT INTO nodes (id, salience, anchor, created_cycle,"
                " last_active_cycle, activations) VALUES (?,?,?,?,?,?)",
                [
                    (
                        n["id"],
                        n["salience"],
                        int(n["anchor"]),
                        n["created_cycle"],
                        n["last_active_cycle"],
                        n["activations"],
                    )
                    for n in data["nodes"]  # type: ignore[union-attr]
                ],
            )
            self._db.executemany(
                "INSERT INTO edges (a, b, weight) VALUES (?,?,?)",
                [tuple(e) for e in data["edges"]],  # type: ignore[union-attr]
            )
            self._db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES ('cycle', ?)",
                (str(data["cycle"]),),
            )

    # ------------------------------------------------------------ 特质

    def load_traits(self, include_retired: bool = False) -> List[Trait]:
        sql = "SELECT * FROM traits"
        if not include_retired:
            sql += " WHERE retired=0"
        sql += " ORDER BY strength DESC"
        out = []
        for r in self._db.execute(sql).fetchall():
            t = Trait(
                id=r["id"],
                text=r["text"],
                strength=float(r["strength"] or 0.0),
                pending=float(r["pending"] or 0.0),
                gate_level=int(r["gate_level"] or 0),
                transient=float(r["transient"] or 0.0),
                momentum=float(r["momentum"] or 0.0),
                inactive_cycles=int(r["inactive_cycles"] or 0),
                warmup_remaining=int(r["warmup_remaining"] or 0),
                from_seed=bool(r["from_seed"]),
                fuzziness=float(r["fuzziness"] or 0.0),
                uncertainty_gate=float(r["uncertainty_gate"] or 0.55),
                dormancy_after=int(r["dormancy_after"] or 24),
                evidence=json.loads(r["evidence"] or "[]"),
                reinforced=int(r["reinforced"] or 0),
                contradicted=int(r["contradicted"] or 0),
                expressed=int(r["expressed"] or 0),
                opportunities=int(r["opportunities"] or 0),
                formed_at=r["formed_at"],
                last_commit_at=r["last_commit_at"],
            )
            # 蓄水池里攒着的来历必须还原，否则质变时指不回去
            try:
                t._staged = json.loads(r["staged"] or "[]")
            except (TypeError, ValueError):
                t._staged = []
            try:
                raw_uncertain = json.loads(r["uncertain"] or "[]")
                t._uncertain = raw_uncertain if isinstance(raw_uncertain, list) else []
            except (TypeError, ValueError):
                t._uncertain = []
            out.append(t)
        return out

    def save_trait(self, trait: Trait, from_seed: bool = False) -> None:
        seed_flag = int(bool(from_seed or trait.from_seed))
        self._db.execute(
            "INSERT INTO traits ("
            " id, text, strength, pending, gate_level, transient, momentum,"
            " inactive_cycles, warmup_remaining, evidence, staged, uncertain,"
            " reinforced, contradicted, expressed, opportunities,"
            " formed_at, last_commit_at, from_seed,"
            " fuzziness, uncertainty_gate, dormancy_after"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET"
            "   text=excluded.text, strength=excluded.strength,"
            "   pending=excluded.pending, gate_level=excluded.gate_level,"
            "   transient=excluded.transient, momentum=excluded.momentum,"
            "   inactive_cycles=excluded.inactive_cycles, warmup_remaining=excluded.warmup_remaining,"
            "   evidence=excluded.evidence, staged=excluded.staged, uncertain=excluded.uncertain,"
            "   reinforced=excluded.reinforced, contradicted=excluded.contradicted,"
            "   expressed=excluded.expressed, opportunities=excluded.opportunities,"
            "   formed_at=excluded.formed_at, last_commit_at=excluded.last_commit_at,"
            "   from_seed=MAX(traits.from_seed, excluded.from_seed),"
            "   fuzziness=excluded.fuzziness,"
            "   uncertainty_gate=excluded.uncertainty_gate,"
            "   dormancy_after=excluded.dormancy_after",
            (
                trait.id,
                trait.text,
                float(trait.strength),
                float(trait.pending),
                int(trait.gate_level),
                float(trait.transient),
                float(trait.momentum),
                int(trait.inactive_cycles),
                int(trait.warmup_remaining),
                json.dumps(trait.evidence, ensure_ascii=False),
                json.dumps(trait._staged, ensure_ascii=False),
                json.dumps(trait._uncertain, ensure_ascii=False),
                int(trait.reinforced),
                int(trait.contradicted),
                int(trait.expressed),
                int(trait.opportunities),
                trait.formed_at,
                trait.last_commit_at,
                seed_flag,
                float(trait.fuzziness),
                float(trait.uncertainty_gate),
                int(trait.dormancy_after),
            ),
        )
        self._db.commit()

    def save_traits(self, traits: Sequence[Trait]) -> None:
        for t in traits:
            self.save_trait(t)

    def retire_trait(self, trait_id: str) -> None:
        """退休一条特质。不删 —— 它的来历还要查得到。"""
        self._db.execute("UPDATE traits SET retired=1 WHERE id=?", (trait_id,))
        self._db.commit()

    def kernel(self) -> List[Trait]:
        """已经硬到成为内核的那几条。不是谁指定的，是长出来的。"""
        return [t for t in self.load_traits() if t.is_kernel]

    # ------------------------------------------------------------ 自述

    def add_narrative(
        self,
        text: str,
        basis: Sequence[str],
        cycle: int = 0,
        kind: str = "derived",
    ) -> int:
        """写入一版自述。

        Args:
            basis: 这一版是从哪些记忆推出来的。空的一律拒绝 ——
                自述必须锚在记忆上，不许凭空，也不许照着上一版改。
            kind: derived 从记忆推导 | rebuilt 从零重建（漂移检测用）
        """
        if not basis:
            raise ValueError("自述必须指明它是从哪些记忆推出来的")
        cur = self._db.execute(
            "INSERT INTO narratives (text, kind, basis, cycle, created_at)"
            " VALUES (?,?,?,?,?)",
            (text, kind, json.dumps(list(basis)), cycle, time.time()),
        )
        self._db.commit()
        return int(cur.lastrowid or 0)

    def current_narrative(self, kind: str = "derived") -> Optional[Dict[str, object]]:
        row = self._db.execute(
            "SELECT * FROM narratives WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)
        ).fetchone()
        return dict(row) if row else None

    def narrative_at(self, n_back: int, kind: str = "derived") -> Optional[Dict[str, object]]:
        """倒数第 n 版自述。

        用于隔代比对：第 4 版跟第 2 版比，而不只跟第 3 版比。
        这是一根从深处直接拉过来的线，让衰减变慢。
        """
        rows = self._db.execute(
            "SELECT * FROM narratives WHERE kind=? ORDER BY id DESC LIMIT ?",
            (kind, n_back + 1),
        ).fetchall()
        return dict(rows[n_back]) if len(rows) > n_back else None

    def narrative_history(self, limit: int = 50) -> List[Dict[str, object]]:
        rows = self._db.execute(
            "SELECT id, kind, cycle, created_at, text FROM narratives"
            " ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ 档案卡

    def set_dossier(
        self,
        key: str,
        value: str,
        source_ids: Sequence[str],
        confidence: float = 0.8,
    ) -> None:
        """写入一条常驻事实。

        旧值不删，标记为被替代。"他曾经是 X，后来变成 Y"本身就是
        重要信息，抹掉就丢了。
        """
        old = self._db.execute("SELECT value FROM dossier WHERE key=?", (key,)).fetchone()
        if old and old["value"] != value:
            self._db.execute(
                "INSERT OR REPLACE INTO dossier"
                " (key, value, superseded_by, source_ids, confidence, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (
                    f"{key}@{int(time.time())}",
                    old["value"],
                    key,
                    "[]",
                    0.0,
                    time.time(),
                ),
            )
        self._db.execute(
            "INSERT OR REPLACE INTO dossier"
            " (key, value, superseded_by, source_ids, confidence, updated_at)"
            " VALUES (?,?,NULL,?,?,?)",
            (key, value, json.dumps(list(source_ids)), confidence, time.time()),
        )
        self._db.commit()

    def dossier(self) -> Dict[str, str]:
        """当前有效的常驻档案。永远在线，不走检索。"""
        rows = self._db.execute(
            "SELECT key, value FROM dossier WHERE superseded_by IS NULL"
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def dossier_history(self, key: str) -> List[Dict[str, object]]:
        """一条档案的变迁史。"""
        rows = self._db.execute(
            "SELECT * FROM dossier WHERE key=? OR superseded_by=?"
            " ORDER BY updated_at",
            (key, key),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ 账

    def log_change(
        self,
        cycle: int,
        kind: str,
        reason: str,
        evidence: Sequence[str],
        target: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> int:
        """记一笔人格变化。

        没有 evidence 一律拒绝 —— 这是那条总原则的最后一道闸门：
        任何改动都必须能指回具体哪几件事，指不出来的不许发生。
        """
        if not evidence:
            raise ValueError(f"人格变化必须有依据：{kind} {target}")
        cur = self._db.execute(
            "INSERT INTO changelog (cycle, kind, target, before, after,"
            " reason, evidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                cycle,
                kind,
                target,
                before,
                after,
                reason,
                json.dumps(list(evidence)),
                time.time(),
            ),
        )
        self._db.commit()
        return int(cur.lastrowid or 0)

    def history(self, limit: int = 100, kind: Optional[str] = None) -> List[Dict[str, object]]:
        """人格演化时间线。它是在哪一天、因为什么，变成现在这样的。"""
        sql = "SELECT * FROM changelog"
        args: List[object] = []
        if kind:
            sql += " WHERE kind=?"
            args.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        out = []
        for r in self._db.execute(sql, args).fetchall():
            d = dict(r)
            d["evidence"] = json.loads(d["evidence"])
            d["when"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(d["created_at"]))
            out.append(d)
        return out

    # ------------------------------------------------------------ 状态

    def get_state(self, key: str, default: str = "") -> str:
        row = self._db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?,?)", (key, str(value))
        )
        self._db.commit()

    def runtime_config(self) -> Dict[str, object]:
        raw = self.get_state("runtime_config", "")
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def set_runtime_config(
        self,
        config: Dict[str, object],
        note: str = "",
        actor: str = "system",
    ) -> int:
        """保存一版运行参数并设为当前生效。"""
        blob = json.dumps(config, ensure_ascii=False, sort_keys=True)
        now = time.time()
        with self._db:
            cur = self._db.execute(
                "INSERT INTO config_versions (actor, note, config_json, created_at)"
                " VALUES (?,?,?,?)",
                (actor, note.strip(), blob, now),
            )
            version_id = int(cur.lastrowid or 0)
            self._db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES ('runtime_config', ?)",
                (blob,),
            )
            self._db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES ('runtime_config_version', ?)",
                (str(version_id),),
            )
        return version_id

    def runtime_config_history(self, limit: int = 20) -> List[Dict[str, object]]:
        rows = self._db.execute(
            "SELECT id, actor, note, config_json, created_at"
            " FROM config_versions ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        out: List[Dict[str, object]] = []
        for r in rows:
            item = dict(r)
            try:
                item["config"] = json.loads(item.pop("config_json"))
            except json.JSONDecodeError:
                item["config"] = {}
                item.pop("config_json", None)
            item["when"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(item["created_at"])))
            out.append(item)
        return out

    def rollback_runtime_config(
        self,
        version_id: int,
        note: str = "",
        actor: str = "rollback",
    ) -> Dict[str, object]:
        row = self._db.execute(
            "SELECT config_json FROM config_versions WHERE id=?",
            (int(version_id),),
        ).fetchone()
        if row is None:
            raise ValueError(f"配置版本不存在: {version_id}")

        try:
            cfg = json.loads(str(row["config_json"]))
        except json.JSONDecodeError as exc:
            raise ValueError(f"配置版本损坏: {version_id}") from exc
        if not isinstance(cfg, dict):
            raise ValueError(f"配置版本格式错误: {version_id}")

        self.set_runtime_config(
            cfg,
            note=(note.strip() or f"rollback to version {version_id}"),
            actor=actor,
        )
        return cfg

    def changelog_window_stats(
        self,
        window_seconds: int = 86400,
        bucket_seconds: int = 3600,
        limit: int = 48,
        kind: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, object]:
        """按时间窗聚合 changelog。"""
        bucket = max(60, int(bucket_seconds))
        window = max(bucket, int(window_seconds))
        cap = max(1, min(int(limit), 512))
        ts = float(now if now is not None else time.time())
        since = ts - float(window)

        sql = (
            "SELECT CAST(created_at / ? AS INTEGER) * ? AS bucket_start,"
            " COUNT(*) AS changes"
            " FROM changelog"
            " WHERE created_at>=?"
        )
        args: List[object] = [bucket, bucket, since]
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        sql += " GROUP BY bucket_start ORDER BY bucket_start DESC LIMIT ?"
        args.append(cap)

        rows = self._db.execute(sql, args).fetchall()
        points: List[Dict[str, object]] = []
        for r in reversed(rows):
            start = float(r["bucket_start"])
            points.append(
                {
                    "start": start,
                    "end": start + float(bucket),
                    "changes": int(r["changes"] or 0),
                }
            )

        return {
            "window_seconds": window,
            "bucket_seconds": bucket,
            "kind": kind or "all",
            "points": points,
        }

    def log_experiment_flags(
        self,
        flags: Dict[str, object],
        note: str = "",
        actor: str = "system",
    ) -> int:
        """记录一次实验参数或开关变更。"""
        blob = json.dumps(flags, ensure_ascii=False, sort_keys=True)
        cur = self._db.execute(
            "INSERT INTO experiment_audit (actor, note, flags_json, created_at)"
            " VALUES (?,?,?,?)",
            (actor, note.strip(), blob, time.time()),
        )
        self._db.commit()
        return int(cur.lastrowid or 0)

    def experiment_history(self, limit: int = 20) -> List[Dict[str, object]]:
        rows = self._db.execute(
            "SELECT id, actor, note, flags_json, created_at"
            " FROM experiment_audit ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        out: List[Dict[str, object]] = []
        for r in rows:
            item = dict(r)
            try:
                item["flags"] = json.loads(item.pop("flags_json"))
            except json.JSONDecodeError:
                item["flags"] = {}
                item.pop("flags_json", None)
            item["when"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(item["created_at"])))
            out.append(item)
        return out

    def experiment_flags(self) -> Dict[str, object]:
        raw = self.get_state("experiment_flags", "")
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def set_experiment_flags(
        self,
        flags: Dict[str, object],
        note: str = "",
        actor: str = "system",
        merge: bool = True,
    ) -> Dict[str, object]:
        base = self.experiment_flags() if merge else {}
        merged = dict(base)
        for k, v in (flags or {}).items():
            merged[str(k)] = v

        blob = json.dumps(merged, ensure_ascii=False, sort_keys=True)
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES ('experiment_flags', ?)",
                (blob,),
            )
        self.log_experiment_flags(merged, note=note, actor=actor)
        return merged

    def begin_recompute_run(
        self,
        mode: str,
        trigger: str = "api",
        from_cycle: int = 0,
        to_cycle: int = 0,
        details: Optional[Dict[str, object]] = None,
    ) -> int:
        """记一笔重算开始。"""
        cur = self._db.execute(
            "INSERT INTO recompute_runs"
            " (mode, trigger, status, from_cycle, to_cycle, details_json, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                str(mode),
                str(trigger),
                "running",
                int(from_cycle),
                int(to_cycle),
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
                time.time(),
            ),
        )
        self._db.commit()
        return int(cur.lastrowid or 0)

    def finish_recompute_run(
        self,
        run_id: int,
        status: str,
        details: Optional[Dict[str, object]] = None,
        to_cycle: Optional[int] = None,
    ) -> None:
        payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
        if to_cycle is None:
            self._db.execute(
                "UPDATE recompute_runs SET status=?, details_json=?, finished_at=? WHERE id=?",
                (str(status), payload, time.time(), int(run_id)),
            )
        else:
            self._db.execute(
                "UPDATE recompute_runs"
                " SET status=?, to_cycle=?, details_json=?, finished_at=?"
                " WHERE id=?",
                (str(status), int(to_cycle), payload, time.time(), int(run_id)),
            )
        self._db.commit()

    def recompute_history(self, limit: int = 20) -> List[Dict[str, object]]:
        rows = self._db.execute(
            "SELECT id, mode, trigger, status, from_cycle, to_cycle, details_json, created_at, finished_at"
            " FROM recompute_runs ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        out: List[Dict[str, object]] = []
        for r in rows:
            item = dict(r)
            try:
                item["details"] = json.loads(item.pop("details_json"))
            except json.JSONDecodeError:
                item["details"] = {}
                item.pop("details_json", None)
            item["when"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(item["created_at"])))
            out.append(item)
        return out

    # ------------------------------------------------------------ 概况

    def stats(self) -> Dict[str, object]:
        e = self._db.execute(
            "SELECT COUNT(*) AS n,"
            " AVG(COALESCE(d.base_salience * d.decay_weight, e.salience)) AS sal,"
            " SUM(e.stood_firm) AS firm"
            " FROM events e LEFT JOIN event_decay d ON d.event_id=e.id"
        ).fetchone()
        t = self._db.execute(
            "SELECT COUNT(*) n, MAX(strength) top FROM traits WHERE retired=0"
        ).fetchone()
        return {
            "事件": e["n"] or 0,
            "平均显著性": round(e["sal"] or 0.0, 3),
            "顶住我的时刻": e["firm"] or 0,
            "特质": t["n"] or 0,
            "最强特质": round(t["top"] or 0.0, 3),
            "内核": len(self.kernel()),
            "连线": self._db.execute("SELECT COUNT(*) n FROM edges").fetchone()["n"],
            "自述版本": self._db.execute(
                "SELECT COUNT(*) n FROM narratives"
            ).fetchone()["n"],
            "变更记录": self._db.execute(
                "SELECT COUNT(*) n FROM changelog"
            ).fetchone()["n"],
            "周期": int(self.get_state("cycle", "0")),
        }

    # ------------------------------------------------------------ 重建

    def wipe_derived(self) -> None:
        """清掉一切派生物，保留 changelog 和自述历史。

        用于从原始日记完全重建。日记没动，所以这个操作是安全的 ——
        这也正是"生熟分离"的意义：熟的坏了就重煮，料还在。
        """
        with self._db:
            for table in ("events", "event_decay", "nodes", "edges", "traits"):
                self._db.execute(f"DELETE FROM {table}")
            self._db.execute("DELETE FROM events_fts")
            self._db.execute(
                "DELETE FROM state WHERE key IN ('cycle', 'decay:last_applied_at')"
            )

    # ------------------------------------------------------------ 生命周期

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Memory":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------- 工具

def _to_event(row: sqlite3.Row) -> Event:
    salience_key = "effective_salience" if "effective_salience" in row.keys() else "salience"
    return Event(
        id=row["id"],
        summary=row["summary"],
        source_ids=json.loads(row["source_ids"]),
        session=row["session"],
        salience=float(row[salience_key]),
        valence=float(row["valence"]),
        questions=json.loads(row["questions"]),
        entities=json.loads(row["entities"]),
        stood_firm=bool(row["stood_firm"]),
        happened_at=float(row["happened_at"]),
        created_at=float(row["created_at"]),
    )



#: 停用词。中文里这些字组出来的二元词满天飞，留着只会让 bm25 失灵。
_STOP = set("的了是在有和也就都而及与这那我你他她它个不很么什怎样很吗呢吧啊呀嗯")


def _tokens(text: str) -> List[str]:
    """把一段文本切成可检索的词。

    中文切二元（"汇报被打断" → 汇报/报被/被打/打断），西文按整词。
    二元而不是单字：单字命中面太宽，几乎每条记忆都能被"的""说"命中，
    bm25 的区分度就没了；二元既保留了"部分匹配"的能力（不需要词典，
    "季度汇报" 和 "上次汇报" 共享 "汇报" 这个词），又不至于滥命中。
    """
    out: List[str] = []
    run: List[str] = []   # 连续汉字
    word: List[str] = []  # 连续西文/数字

    def flush_cjk() -> None:
        if not run:
            return
        if len(run) == 1:
            if run[0] not in _STOP:
                out.append(run[0])
        else:
            for i in range(len(run) - 1):
                gram = run[i] + run[i + 1]
                # 两个字都是虚词的二元词不要
                if run[i] in _STOP and run[i + 1] in _STOP:
                    continue
                out.append(gram)
        run.clear()

    def flush_word() -> None:
        if word:
            out.append("".join(word).lower())
            word.clear()

    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            flush_word()
            run.append(ch)
        elif ch.isalnum():
            flush_cjk()
            word.append(ch)
        else:
            flush_cjk()
            flush_word()
    flush_cjk()
    flush_word()
    return out


def _segment(text: str) -> str:
    """入索引前的分词结果，空格分隔。"""
    return " ".join(_tokens(text))


def _fts_terms(query: str) -> str:
    """把自然语言拆成 FTS5 能吃的 OR 查询。

    索引侧和查询侧用同一个分词函数 —— 两边规则必须一致，
    否则存进去的词和查出来的词对不上。
    """
    seen: set[str] = set()
    uniq = [t for t in _tokens(query) if not (t in seen or seen.add(t))]
    if not uniq:
        return ""
    return " OR ".join(f'"{t}"' for t in uniq[:48])


def _merge_sparse_points(
    points: Sequence[Dict[str, object]],
    bucket_seconds: int,
    min_events: int = 2,
    max_span_buckets: int = 3,
) -> List[Dict[str, object]]:
    """把稀疏小桶做轻量归并，减少 dashboard 时间窗碎片。"""
    if not points:
        return []

    merged: List[Dict[str, object]] = []
    cur: Optional[Dict[str, object]] = None
    span = 0
    step = float(max(60, int(bucket_seconds)))

    for p in points:
        item = {
            "start": float(p.get("start") or 0.0),
            "end": float(p.get("end") or 0.0),
            "events": int(p.get("events") or 0),
            "stood_firm": int(p.get("stood_firm") or 0),
            "avg_salience": float(p.get("avg_salience") or 0.0),
        }
        if cur is None:
            cur = dict(item)
            span = 1
            continue

        contiguous = abs(float(item["start"]) - float(cur["end"])) <= step
        sparse = int(cur["events"]) < int(min_events) or int(item["events"]) < int(min_events)
        if contiguous and sparse and span < max_span_buckets:
            total = int(cur["events"]) + int(item["events"])
            if total > 0:
                cur["avg_salience"] = round(
                    (
                        float(cur["avg_salience"]) * int(cur["events"])
                        + float(item["avg_salience"]) * int(item["events"])
                    )
                    / total,
                    4,
                )
            cur["events"] = total
            cur["stood_firm"] = int(cur["stood_firm"]) + int(item["stood_firm"])
            cur["end"] = float(item["end"])
            span += 1
        else:
            merged.append(cur)
            cur = dict(item)
            span = 1

    if cur is not None:
        merged.append(cur)

    return merged