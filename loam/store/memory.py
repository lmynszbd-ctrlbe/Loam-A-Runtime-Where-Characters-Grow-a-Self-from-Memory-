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
from typing import Dict, List, Optional, Sequence, Tuple

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
    -- 已提交的来历
    evidence       TEXT    NOT NULL DEFAULT '[]',
    -- 蓄水池里攒着但还没质变的来历。不能丢。
    staged         TEXT    NOT NULL DEFAULT '[]',
    reinforced     INTEGER NOT NULL DEFAULT 0,
    contradicted   INTEGER NOT NULL DEFAULT 0,
    expressed      INTEGER NOT NULL DEFAULT 0,
    opportunities  INTEGER NOT NULL DEFAULT 0,
    formed_at      TEXT,
    last_commit_at TEXT,
    -- 来自角色卡的种子特质。土壤，全程保留。
    from_seed      INTEGER NOT NULL DEFAULT 0,
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
        for trig in TRIGGERS:
            self._db.execute(trig)
        self._db.commit()

    # ------------------------------------------------------------ 事件

    def add_event(self, event: Event) -> None:
        """写入一条情景记忆。必须有来历。"""
        if not event.source_ids:
            raise ValueError("事件必须指回原始日记（source_ids 不可为空）")
        now = time.time()
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
        self._db.commit()
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
        row = self._db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return _to_event(row) if row else None

    def get_events(self, ids: Sequence[str]) -> List[Event]:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self._db.execute(
            f"SELECT * FROM events WHERE id IN ({marks})", list(ids)
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
        sql = "SELECT * FROM events"
        args: List[object] = []
        if session:
            sql += " WHERE session=?"
            args.append(session)
        sql += " ORDER BY happened_at DESC LIMIT ?"
        args.append(limit)
        return [_to_event(r) for r in self._db.execute(sql, args).fetchall()]

    def stood_firm_events(self, limit: int = 20) -> List[Event]:
        """它顶住了我的那些时刻。

        这是它长出"我"的唯一训练信号。一个人的自我不是在被认同的
        时候确立的，是在压力下没让步的时候。所以单独开一个查询。
        """
        rows = self._db.execute(
            "SELECT * FROM events WHERE stood_firm=1"
            " ORDER BY salience DESC, happened_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_to_event(r) for r in rows]

    def update_salience(self, event_id: str, salience: float) -> None:
        """重估重要性。睡眠时做 —— 有些事当时不觉得，后来才知道重要。"""
        self._db.execute(
            "UPDATE events SET salience=? WHERE id=?",
            (max(0.0, min(1.0, salience)), event_id),
        )
        self._db.commit()

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
                strength=r["strength"],
                pending=r["pending"],
                evidence=json.loads(r["evidence"]),
                reinforced=r["reinforced"],
                contradicted=r["contradicted"],
                expressed=r["expressed"],
                opportunities=r["opportunities"],
                formed_at=r["formed_at"],
                last_commit_at=r["last_commit_at"],
            )
            # 蓄水池里攒着的来历必须还原，否则质变时指不回去
            t._staged = json.loads(r["staged"])
            out.append(t)
        return out

    def save_trait(self, trait: Trait, from_seed: bool = False) -> None:
        self._db.execute(
            "INSERT INTO traits (id, text, strength, pending, evidence, staged,"
            " reinforced, contradicted, expressed, opportunities,"
            " formed_at, last_commit_at, from_seed)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET"
            "   text=excluded.text, strength=excluded.strength,"
            "   pending=excluded.pending, evidence=excluded.evidence,"
            "   staged=excluded.staged, reinforced=excluded.reinforced,"
            "   contradicted=excluded.contradicted, expressed=excluded.expressed,"
            "   opportunities=excluded.opportunities, formed_at=excluded.formed_at,"
            "   last_commit_at=excluded.last_commit_at",
            (
                trait.id,
                trait.text,
                trait.strength,
                trait.pending,
                json.dumps(trait.evidence),
                json.dumps(trait._staged),
                trait.reinforced,
                trait.contradicted,
                trait.expressed,
                trait.opportunities,
                trait.formed_at,
                trait.last_commit_at,
                int(from_seed),
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

    # ------------------------------------------------------------ 概况

    def stats(self) -> Dict[str, object]:
        e = self._db.execute(
            "SELECT COUNT(*) n, AVG(salience) sal, SUM(stood_firm) firm FROM events"
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
            for table in ("events", "nodes", "edges", "traits"):
                self._db.execute(f"DELETE FROM {table}")
            self._db.execute("DELETE FROM events_fts")
            self._db.execute("DELETE FROM state WHERE key='cycle'")

    # ------------------------------------------------------------ 生命周期

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Memory":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------- 工具


def _to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        summary=row["summary"],
        source_ids=json.loads(row["source_ids"]),
        session=row["session"],
        salience=float(row["salience"]),
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