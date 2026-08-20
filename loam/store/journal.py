"""原始日记 —— 不可修改的底稿。

这是整个 loam 唯一的真相来源。任何一轮对话进来，一字不改地落盘，
永不删除、永不改写。它平时不参与检索，就摆在那儿。

存在的理由有三个：

1. 上面几层坏了，可以从这儿重新推一遍。
2. 人格的每一次变化都必须能指回这里的某几条 —— 这是防漂移和
   防谄媚的唯一根本手段。
3. 定期从零重建自我模型时，输入是这里，不是自我模型的上一版。
   这条线直接拉到地面，是那个"本来不存在的底稿"。

写入必须快到几乎不可能失败：不调模型，不判断重要性，不做任何加工。
生的和熟的分开 —— 煮的活儿交给后台，料先保住。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

MAX_INGEST_JOB_ATTEMPTS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    character    TEXT    NOT NULL,
    session      TEXT    NOT NULL,
    turn         INTEGER NOT NULL,
    role         TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    fingerprint  TEXT    NOT NULL,
    client       TEXT,
    model        TEXT,
    meta         TEXT,
    wrote_at     REAL    NOT NULL,
    digested     INTEGER NOT NULL DEFAULT 0
);

-- 同一段话抓两次只留一条，所以补录可以放心地反复跑
CREATE UNIQUE INDEX IF NOT EXISTS idx_fingerprint
    ON entries(character, fingerprint);

CREATE INDEX IF NOT EXISTS idx_session_turn
    ON entries(character, session, turn);

CREATE INDEX IF NOT EXISTS idx_undigested
    ON entries(character, digested, id);

-- 每个会话的游标，用于发现漏轮
CREATE TABLE IF NOT EXISTS cursors (
    character     TEXT NOT NULL,
    session       TEXT NOT NULL,
    last_turn     INTEGER NOT NULL,
    last_seen_at  REAL    NOT NULL,
    PRIMARY KEY (character, session)
);

-- 记下每一次"本该收到却没收到"的缺口。
-- 这些记录攒起来就是一套真实场景里的测试题，免费的，别浪费。
CREATE TABLE IF NOT EXISTS gaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    character   TEXT    NOT NULL,
    session     TEXT    NOT NULL,
    from_turn   INTEGER NOT NULL,
    to_turn     INTEGER NOT NULL,
    noticed_at  REAL    NOT NULL,
    filled      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_open_gaps
    ON gaps(character, filled);

-- ---------------------------------------------------------------- 证据缓冲与异步 ingest 队列
CREATE TABLE IF NOT EXISTS pending_evidence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    character     TEXT    NOT NULL,
    session       TEXT    NOT NULL,
    turn          INTEGER NOT NULL,
    role          TEXT    NOT NULL,
    content       TEXT    NOT NULL,
    evidence_hash TEXT    NOT NULL,
    client        TEXT,
    model         TEXT,
    meta          TEXT,
    wrote_at      REAL    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    created_at    REAL    NOT NULL,
    processed_at  REAL,
    job_id        INTEGER
);

-- 幂等：同 session + 同证据哈希只入一次
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_evidence_unique
    ON pending_evidence(character, session, evidence_hash);

CREATE INDEX IF NOT EXISTS idx_pending_evidence_status
    ON pending_evidence(character, status, id);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    character   TEXT    NOT NULL,
    session     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  REAL    NOT NULL,
    updated_at  REAL    NOT NULL,
    started_at  REAL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status
    ON ingest_jobs(character, status, id);

-- 每个 session 同时最多一条 open job（pending/processing）
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_jobs_open_session
    ON ingest_jobs(character, session)
    WHERE status IN ('pending', 'processing');
"""


@dataclass
class Entry:
    """日记里的一条。"""

    id: int
    character: str
    session: str
    turn: int
    role: str
    content: str
    fingerprint: str
    client: Optional[str]
    model: Optional[str]
    meta: Dict[str, object]
    wrote_at: float
    digested: bool

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.wrote_at))


def fingerprint(character: str, session: str, turn: int, role: str, content: str) -> str:
    """内容指纹。用于去重 —— 同一段话抓多少次都只存一条。

    把会话和轮次也算进去，是因为同一句话（"好"、"嗯"）在不同轮次
    是不同的事件，不该被当成重复。
    """
    raw = f"{character}\x00{session}\x00{turn}\x00{role}\x00{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def evidence_fingerprint(session: str, role: str, content: str) -> str:
    """pending 证据指纹（不含 turn），用于幂等去重。

    设计约束：UNIQUE(session_id, evidence_hash) 冲突时直接跳过。
    """
    normalized = " ".join((content or "").strip().split())
    raw = f"{session}\x00{(role or '').strip().lower()}\x00{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class Journal:
    """原始日记。只增不改不删。

    用法::

        with Journal("~/loam/characters/xx/journal.db") as j:
            j.append("xx", "session-1", 1, "user", "你好")
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # WAL 让写入更难失败，也允许后台边煮边有新料进来
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)
        self._db.commit()

    # ------------------------------------------------------------ 写入

    def append(
        self,
        character: str,
        session: str,
        turn: int,
        role: str,
        content: str,
        client: Optional[str] = None,
        model: Optional[str] = None,
        meta: Optional[Dict[str, object]] = None,
        wrote_at: Optional[float] = None,
    ) -> Optional[int]:
        """落盘一条。

        Returns:
            新条目的 id；如果这条已经存在（指纹重复）则返回 None。
        """
        fp = fingerprint(character, session, turn, role, content)
        try:
            cur = self._db.execute(
                "INSERT INTO entries"
                " (character, session, turn, role, content, fingerprint,"
                "  client, model, meta, wrote_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    character,
                    session,
                    turn,
                    role,
                    content,
                    fp,
                    client,
                    model,
                    json.dumps(meta or {}, ensure_ascii=False),
                    wrote_at if wrote_at is not None else time.time(),
                ),
            )
        except sqlite3.IntegrityError:
            return None  # 已经有了，补录重复跑是安全的
        self._db.commit()
        return int(cur.lastrowid or 0)

    def append_batch(
        self,
        character: str,
        session: str,
        turns: Sequence[Dict[str, object]],
        client: Optional[str] = None,
        model: Optional[str] = None,
        commit: bool = True,
    ) -> int:
        """批量落盘。用于握手时补交、或从客户端聊天记录里补录。

        Args:
            turns: 每项形如 {"turn": 5, "role": "user", "content": "...",
                   可选 "wrote_at": 时间戳, "meta": {...}}
            commit: True 表示本方法内提交；False 表示由外层事务统一提交。

        Returns:
            实际新增的条数（重复的不计）。
        """
        added = 0
        now = time.time()
        for t in turns:
            fp = fingerprint(
                character,
                session,
                int(t["turn"]),  # type: ignore[arg-type]
                str(t["role"]),
                str(t["content"]),
            )
            try:
                self._db.execute(
                    "INSERT INTO entries"
                    " (character, session, turn, role, content, fingerprint,"
                    "  client, model, meta, wrote_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        character,
                        session,
                        int(t["turn"]),  # type: ignore[arg-type]
                        str(t["role"]),
                        str(t["content"]),
                        fp,
                        client,
                        model,
                        json.dumps(t.get("meta") or {}, ensure_ascii=False),
                        float(t.get("wrote_at") or now),  # type: ignore[arg-type]
                    ),
                )
                added += 1
            except sqlite3.IntegrityError:
                continue
        if commit:
            self._db.commit()
        return added

    # ------------------------------------------------------------ pending 证据与 ingest 队列

    def enqueue_pending_evidence(
        self,
        character: str,
        session: str,
        turns: Sequence[Dict[str, object]],
        client: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, int]:
        """原子地：证据落盘 + 建立（或复用）session 队列任务。"""
        now = time.time()
        added = 0
        deduped = 0

        with self._db:
            for t in turns:
                role = str(t.get("role") or "").strip()
                content = str(t.get("content") or "").strip()
                if not role or not content:
                    continue
                ev_hash = evidence_fingerprint(session, role, content)
                try:
                    self._db.execute(
                        "INSERT INTO pending_evidence"
                        " (character, session, turn, role, content, evidence_hash,"
                        "  client, model, meta, wrote_at, status, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            character,
                            session,
                            int(t.get("turn") or 0),
                            role,
                            content,
                            ev_hash,
                            client,
                            model,
                            json.dumps(t.get("meta") or {}, ensure_ascii=False),
                            float(t.get("wrote_at") or now),
                            "pending",
                            now,
                        ),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    deduped += 1
            # 只有存在待处理证据时，才需要保持 open job。
            has_pending = self._db.execute(
                "SELECT 1 FROM pending_evidence"
                " WHERE character=? AND session=? AND status='pending'"
                " ORDER BY id LIMIT 1",
                (character, session),
            ).fetchone()
            if has_pending is not None:
                row = self._db.execute(
                    "SELECT id FROM ingest_jobs"
                    " WHERE character=? AND session=? AND status IN ('pending','processing')"
                    " ORDER BY id LIMIT 1",
                    (character, session),
                ).fetchone()
                if row is None:
                    self._db.execute(
                        "INSERT INTO ingest_jobs"
                        " (character, session, status, attempts, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?)",
                        (character, session, "pending", 0, now, now),
                    )


        queue = self.queue_stats(character)
        return {
            "added": added,
            "deduped": deduped,
            "pending_evidence": int(queue.get("pending_evidence", 0)),
            "jobs_pending": int(queue.get("jobs_pending", 0)),
            "jobs_processing": int(queue.get("jobs_processing", 0)),
        }

    def recover_processing_jobs(self, character: str) -> int:
        """重启恢复：把遗留 processing 任务打回 pending。"""
        now = time.time()
        cur = self._db.execute(
            "UPDATE ingest_jobs SET status='pending', updated_at=?"
            " WHERE character=? AND status='processing'",
            (now, character),
        )
        self._db.commit()
        return int(cur.rowcount or 0)

    def queue_stats(self, character: str) -> Dict[str, int]:
        pending = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE character=? AND status='pending'",
            (character,),
        ).fetchone()["n"]
        processing = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE character=? AND status='processing'",
            (character,),
        ).fetchone()["n"]
        failed = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE character=? AND status='failed'",
            (character,),
        ).fetchone()["n"]
        pending_ev = self._db.execute(
            "SELECT COUNT(*) n FROM pending_evidence"
            " WHERE character=? AND status='pending'",
            (character,),
        ).fetchone()["n"]
        return {
            "jobs_pending": int(pending or 0),
            "jobs_processing": int(processing or 0),
            "jobs_failed": int(failed or 0),
            "pending_evidence": int(pending_ev or 0),
        }

    def pending_evidence_count(self, character: str) -> int:
        """只统计未处理完毕证据。"""
        row = self._db.execute(
            "SELECT COUNT(*) n FROM pending_evidence"
            " WHERE character=? AND status='pending'",
            (character,),
        ).fetchone()
        return int(row["n"] or 0)

    def _claim_next_job(self, character: str) -> Optional[sqlite3.Row]:
        now = time.time()
        self._db.execute("BEGIN IMMEDIATE")
        row = self._db.execute(
            "SELECT j.id, j.session, j.attempts FROM ingest_jobs j"
            " WHERE j.character=? AND j.status='pending'"
            "   AND j.session NOT IN ("
            "       SELECT session FROM ingest_jobs"
            "       WHERE character=? AND status='processing'"
            "   )"
            " ORDER BY j.id LIMIT 1",
            (character, character),
        ).fetchone()
        if row is None:
            self._db.execute("COMMIT")
            return None

        cur = self._db.execute(
            "UPDATE ingest_jobs SET status='processing', attempts=attempts+1,"
            " started_at=COALESCE(started_at, ?), updated_at=?"
            " WHERE id=? AND status='pending'",
            (now, now, int(row["id"])),
        )
        if (cur.rowcount or 0) != 1:
            self._db.execute("ROLLBACK")
            return None
        self._db.execute("COMMIT")
        return row

    def process_one_ingest_job(self, character: str) -> Optional[Dict[str, Any]]:
        """处理一条队列任务：pending_evidence -> entries。"""
        job = self._claim_next_job(character)
        if job is None:
            return None

        job_id = int(job["id"])
        session = str(job["session"])
        now = time.time()

        try:
            rows = self._db.execute(
                "SELECT id, turn, role, content, meta, wrote_at, client, model"
                " FROM pending_evidence"
                " WHERE character=? AND session=? AND status='pending'"
                " ORDER BY id LIMIT 500",
                (character, session),
            ).fetchall()

            # 端到端原子：entries 写入 + pending 标记 + job 状态，在同一事务里完成。
            with self._db:
                if not rows:
                    self._db.execute(
                        "UPDATE ingest_jobs SET status='done', finished_at=?, updated_at=?, error=NULL"
                        " WHERE id=?",
                        (now, now, job_id),
                    )
                    return {
                        "job_id": job_id,
                        "session": session,
                        "evidence": 0,
                        "entries_added": 0,
                        "done": True,
                    }

                turns: List[Dict[str, object]] = []
                evidence_ids: List[int] = []
                client = None
                model = None
                for r in rows:
                    evidence_ids.append(int(r["id"]))
                    turns.append(
                        {
                            "turn": int(r["turn"]),
                            "role": str(r["role"]),
                            "content": str(r["content"]),
                            "wrote_at": float(r["wrote_at"]),
                            "meta": json.loads(r["meta"] or "{}"),
                        }
                    )
                    if client is None:
                        client = r["client"]
                    if model is None:
                        model = r["model"]

                added = self.append_batch(
                    character,
                    session,
                    turns,
                    client=(str(client) if client else None),
                    model=(str(model) if model else None),
                    commit=False,
                )

                self._db.executemany(
                    "UPDATE pending_evidence"
                    " SET status='processed', processed_at=?, job_id=?"
                    " WHERE id=?",
                    [(now, job_id, i) for i in evidence_ids],
                )
                self._db.execute(
                    "UPDATE ingest_jobs"
                    " SET status='done', finished_at=?, updated_at=?, error=NULL"
                    " WHERE id=?",
                    (now, now, job_id),
                )

                remain = self._db.execute(
                    "SELECT COUNT(*) n FROM pending_evidence"
                    " WHERE character=? AND session=? AND status='pending'",
                    (character, session),
                ).fetchone()["n"]
                open_job = self._db.execute(
                    "SELECT id FROM ingest_jobs"
                    " WHERE character=? AND session=? AND status IN ('pending','processing')"
                    " ORDER BY id LIMIT 1",
                    (character, session),
                ).fetchone()
                if remain and open_job is None:
                    self._db.execute(
                        "INSERT INTO ingest_jobs"
                        " (character, session, status, attempts, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?)",
                        (character, session, "pending", 0, now, now),
                    )

                return {
                    "job_id": job_id,
                    "session": session,
                    "evidence": len(evidence_ids),
                    "entries_added": added,
                    "done": True,
                }
        except Exception as exc:  # noqa: BLE001
            retryable = False
            try:
                attempt_row = self._db.execute(
                    "SELECT attempts FROM ingest_jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                attempts = int(attempt_row["attempts"] if attempt_row else 1)
                retryable = attempts < MAX_INGEST_JOB_ATTEMPTS
                status = "pending" if retryable else "failed"
                self._db.execute(
                    "UPDATE ingest_jobs"
                    " SET status=?, error=?, updated_at=?, finished_at=?"
                    " WHERE id=?",
                    (status, f"{type(exc).__name__}: {exc}", now, now, job_id),
                )
                self._db.commit()
            except Exception:
                pass
            return {
                "job_id": job_id,
                "session": session,
                "done": False,
                "retryable": retryable,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def drain_ingest_jobs(self, character: str, max_jobs: int = 8) -> Dict[str, int]:
        done = 0
        failed = 0
        evidence = 0
        entries = 0
        for _ in range(max_jobs):
            r = self.process_one_ingest_job(character)
            if not r:
                break
            if r.get("done"):
                done += 1
                evidence += int(r.get("evidence") or 0)
                entries += int(r.get("entries_added") or 0)
            else:
                failed += 1
        out = self.queue_stats(character)
        out.update(
            {
                "jobs_done_now": done,
                "jobs_failed_now": failed,
                "evidence_processed_now": evidence,
                "entries_added_now": entries,
            }
        )
        return out

    # ------------------------------------------------------------ 漏轮检测

    def observe_turn(self, character: str, session: str, turn: int) -> Optional[tuple[int, int]]:
        """记录看到的轮次，顺便检查中间有没有缺口。

        客户端每次调用都带一个递增的轮次号。这次来的是 5，上次是 3，
        中间少了 4 —— 立刻就知道漏了，而且知道漏在哪。

        Returns:
            如果发现缺口，返回 (缺失起始轮, 缺失结束轮)；否则 None。
        """
        row = self._db.execute(
            "SELECT last_turn FROM cursors WHERE character=? AND session=?",
            (character, session),
        ).fetchone()

        gap: Optional[tuple[int, int]] = None
        if row is not None:
            last = int(row["last_turn"])
            if turn > last + 1:
                gap = (last + 1, turn - 1)
                self._db.execute(
                    "INSERT INTO gaps (character, session, from_turn, to_turn, noticed_at)"
                    " VALUES (?,?,?,?,?)",
                    (character, session, gap[0], gap[1], time.time()),
                )

        self._db.execute(
            "INSERT INTO cursors (character, session, last_turn, last_seen_at)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(character, session) DO UPDATE SET"
            "   last_turn=MAX(last_turn, excluded.last_turn),"
            "   last_seen_at=excluded.last_seen_at",
            (character, session, turn, time.time()),
        )
        self._db.commit()
        return gap

    def open_gaps(self, character: str) -> List[Dict[str, object]]:
        """还没补上的缺口。下次被调用时可以反向索要这些轮次。"""
        rows = self._db.execute(
            "SELECT id, session, from_turn, to_turn, noticed_at FROM gaps"
            " WHERE character=? AND filled=0 ORDER BY id",
            (character,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close_gap(self, gap_id: int) -> None:
        self._db.execute("UPDATE gaps SET filled=1 WHERE id=?", (gap_id,))
        self._db.commit()

    def reconcile_gaps(self, character: str) -> int:
        """检查已登记的缺口是否已经被补齐（比如补录导入之后）。

        Returns:
            本次关闭的缺口数。
        """
        closed = 0
        for gap in self.open_gaps(character):
            need = int(gap["to_turn"]) - int(gap["from_turn"]) + 1  # type: ignore[arg-type]
            got = self._db.execute(
                "SELECT COUNT(DISTINCT turn) AS n FROM entries"
                " WHERE character=? AND session=? AND turn BETWEEN ? AND ?",
                (character, gap["session"], gap["from_turn"], gap["to_turn"]),
            ).fetchone()["n"]
            if got >= need:
                self.close_gap(int(gap["id"]))  # type: ignore[arg-type]
                closed += 1
        return closed

    def stale_sessions(self, character: str, idle_seconds: float = 900.0) -> List[Dict[str, object]]:
        """绑定着但很久没动静的会话 —— 疑似断流。

        由 loam 自己的后台定期检查，不依赖任何客户端。
        """
        cutoff = time.time() - idle_seconds
        rows = self._db.execute(
            "SELECT session, last_turn, last_seen_at FROM cursors"
            " WHERE character=? AND last_seen_at < ?",
            (character, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ 读取

    def read(
        self,
        character: str,
        session: Optional[str] = None,
        since_id: int = 0,
        limit: int = 200,
    ) -> List[Entry]:
        """按写入顺序读。"""
        sql = "SELECT * FROM entries WHERE character=? AND id>?"
        args: List[object] = [character, since_id]
        if session is not None:
            sql += " AND session=?"
            args.append(session)
        sql += " ORDER BY id LIMIT ?"
        args.append(limit)
        return [_to_entry(r) for r in self._db.execute(sql, args).fetchall()]

    def read_range(
        self,
        character: str,
        session: str,
        from_turn: int,
        to_turn: int,
    ) -> List[Entry]:
        rows = self._db.execute(
            "SELECT * FROM entries WHERE character=? AND session=?"
            " AND turn BETWEEN ? AND ? ORDER BY turn, id",
            (character, session, from_turn, to_turn),
        ).fetchall()
        return [_to_entry(r) for r in rows]

    def undigested(self, character: str, limit: int = 100) -> List[Entry]:
        """还没被煮过的生料。后台按这个队列慢慢消化。

        煮的过程可能失败、可能被中断、可能需要重做 —— 都没关系，
        料还在，随时能重新煮一遍。
        """
        rows = self._db.execute(
            "SELECT * FROM entries WHERE character=? AND digested=0"
            " ORDER BY id LIMIT ?",
            (character, limit),
        ).fetchall()
        return [_to_entry(r) for r in rows]

    def mark_digested(self, ids: Sequence[int]) -> None:
        """标记为已消化。注意：只改这一个标志位，内容本身永不改动。"""
        if not ids:
            return
        self._db.executemany(
            "UPDATE entries SET digested=1 WHERE id=?", [(i,) for i in ids]
        )
        self._db.commit()

    def reset_digestion(self, character: str, since_id: int = 0) -> int:
        """把生料标记全部重置 —— 用于从原始日记重新推导一遍。

        这是那条"定期从零重建"的入口：不看任何一版自我模型，
        从头再煮一次，然后跟当前的比。差出去的那部分就是漂移。
        """
        cur = self._db.execute(
            "UPDATE entries SET digested=0 WHERE character=? AND id>?",
            (character, since_id),
        )
        self._db.commit()
        return cur.rowcount

    def iter_all(self, character: str, chunk: int = 500) -> Iterator[Entry]:
        """遍历一个角色的全部日记。用于从零重建。"""
        last = 0
        while True:
            batch = self.read(character, since_id=last, limit=chunk)
            if not batch:
                return
            for e in batch:
                yield e
            last = batch[-1].id

    # ------------------------------------------------------------ 概况

    def stats(self, character: Optional[str] = None) -> Dict[str, object]:
        where = "WHERE character=?" if character else ""
        args = (character,) if character else ()
        row = self._db.execute(
            f"SELECT COUNT(*) n, SUM(LENGTH(content)) chars,"
            f" MIN(wrote_at) first, MAX(wrote_at) last,"
            f" SUM(digested) done FROM entries {where}",
            args,
        ).fetchone()
        sessions = self._db.execute(
            f"SELECT COUNT(DISTINCT session) n FROM entries {where}", args
        ).fetchone()["n"]
        gaps = self._db.execute(
            "SELECT COUNT(*) n FROM gaps WHERE filled=0"
            + (" AND character=?" if character else ""),
            args,
        ).fetchone()["n"]

        pending_ev = self._db.execute(
            "SELECT COUNT(*) n FROM pending_evidence WHERE status='pending'"
            + (" AND character=?" if character else ""),
            args,
        ).fetchone()["n"]
        jobs_pending = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE status='pending'"
            + (" AND character=?" if character else ""),
            args,
        ).fetchone()["n"]
        jobs_processing = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE status='processing'"
            + (" AND character=?" if character else ""),
            args,
        ).fetchone()["n"]
        jobs_failed = self._db.execute(
            "SELECT COUNT(*) n FROM ingest_jobs WHERE status='failed'"
            + (" AND character=?" if character else ""),
            args,
        ).fetchone()["n"]

        n = row["n"] or 0
        return {
            "条数": n,
            "字数": row["chars"] or 0,
            "会话数": sessions,
            "已消化": row["done"] or 0,
            "待消化": n - (row["done"] or 0),
            "未补缺口": gaps,
            "待处理证据": pending_ev or 0,
            "队列待处理": jobs_pending or 0,
            "队列处理中": jobs_processing or 0,
            "队列失败": jobs_failed or 0,
            "最早": _fmt(row["first"]),
            "最近": _fmt(row["last"]),
        }

    def characters(self) -> List[str]:
        rows = self._db.execute(
            "SELECT DISTINCT character FROM entries ORDER BY character"
        ).fetchall()
        return [r["character"] for r in rows]

    # ------------------------------------------------------------ 生命周期

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------- 工具


def _to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=int(row["id"]),
        character=row["character"],
        session=row["session"],
        turn=int(row["turn"]),
        role=row["role"],
        content=row["content"],
        fingerprint=row["fingerprint"],
        client=row["client"],
        model=row["model"],
        meta=json.loads(row["meta"] or "{}"),
        wrote_at=float(row["wrote_at"]),
        digested=bool(row["digested"]),
    )


def _fmt(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))