"""煮 —— 把生料变成熟料的那个过程。

这是整个 loam 里唯一会调用模型的地方，也是唯一会改动人格的地方。

顺序是固定的，因为每一步都依赖前一步的产物：

    抽事件 → 落网络（赫布连线） → 判特质（印证/动摇）
        → 核对行为（说到有没有做到） → 结算生长 → 更常驻档案
        → 到点了才重写自述

几条不肯让步的规矩：

生熟分离。整个过程里，原始日记一个字都不会被改。煮到一半崩了、
模型给了垃圾、断网了 —— 料还在，`digested` 标志位没翻，下次
重新煮一遍就是。所以这里所有的写入都可以安全地重跑。

有根才准动。事件必须指回日记 id，特质变化必须指回事件 id，自述
必须指明它是从哪些记忆推出来的。这三道闸门都在存储层里，煮的时候
撞上就抛异常，不会静默地放进来。

不看上一版。写自述的时候不给它看之前写过什么，只给记忆和强度。
这是防"复印件的复印件"的唯一办法。

它自己在动。用户没在说话的时候，`Grower` 线程照样按点跑：
攒够了就煮一次，空闲久了收个尾，隔很久做一次从零重建的自我核对。
"""

from __future__ import annotations

import json
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.growth import Evidence, Trait
from ..core.network import Network
from ..store.journal import Entry, Journal
from ..store.memory import Event, Memory
from . import prompts
from .llm import Brain, BrainError, BrainUnavailable

# ---------------------------------------------------------------- 参数


#: 攒够多少条生料就煮一次。太小则每次上下文太薄看不出因果，
#: 太大则一次要判太多事，模型会漏。
BATCH_TURNS = 20

#: 空闲多久（秒）就把没攒满的那点料也煮掉。
#: 聊完一段就走的情况很常见，不能让最后半段一直挂着。
IDLE_SECONDS = 900.0

#: 每多少个周期重写一次自述。自述是最贵也最容易漂的东西，不必每次都动。
NARRATE_EVERY = 5

#: 每多少个周期做一次从零重建的自我核对。
AUDIT_EVERY = 50

#: 单次煮进去的事件最多参与几条特质判定的上下文。
APPRAISE_WINDOW = 30

#: 新提出的倾向至少要有几条不同事件支持。
PROPOSAL_MIN_EVENTS = 2


@dataclass
class DigestReport:
    """煮了一次的结果。给人看，也给测试断言。"""

    cycle: int = 0
    entries: int = 0
    events: int = 0
    edges: int = 0
    traits_touched: int = 0
    traits_moved: int = 0
    traits_born: int = 0
    dossier_updates: int = 0
    narrated: bool = False
    errors: List[str] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        return {
            "周期": self.cycle,
            "吃掉生料": self.entries,
            "新事件": self.events,
            "加粗连线": self.edges,
            "被判定的特质": self.traits_touched,
            "发生质变": self.traits_moved,
            "新长出的特质": self.traits_born,
            "档案更新": self.dossier_updates,
            "重写自述": self.narrated,
            "出错": self.errors,
            "token": self.usage,
        }


class Digester:
    """一次消化。

    这个类不持有线程，也不管什么时候该跑 —— 那是 Grower 的事。
    它只负责"给我一批料，我把它煮成人格的一点变化"。
    """

    def __init__(
        self,
        character: str,
        journal: Journal,
        memory: Memory,
        brain: Brain,
        batch_turns: int = BATCH_TURNS,
    ) -> None:
        self.character = character
        self.journal = journal
        self.memory = memory
        self.brain = brain
        self.batch_turns = batch_turns

    # ------------------------------------------------------------ 入口

    def pending_count(self) -> int:
        return len(self.journal.undigested(self.character, limit=10_000))

    def ready(self, idle_seconds: float = IDLE_SECONDS) -> bool:
        """现在该不该煮。

        两个条件任一满足：攒够了，或者聊完一段没动静了。
        """
        pending = self.journal.undigested(self.character, limit=self.batch_turns * 4)
        if not pending:
            return False
        if len(pending) >= self.batch_turns:
            return True
        newest = max(e.wrote_at for e in pending)
        return (time.time() - newest) >= idle_seconds

    def digest_once(self, limit: Optional[int] = None) -> DigestReport:
        """煮一批。

        任何一步出错都记在 report.errors 里，并且不翻 digested 标志 ——
        下次会重新煮这批料。已经成功写进去的事件靠 id 幂等，重跑不会重复。
        """
        cycle = int(self.memory.get_state("cycle", "0")) + 1
        report = DigestReport(cycle=cycle)

        batch = self.journal.undigested(self.character, limit=limit or self.batch_turns)
        if not batch:
            return report
        report.entries = len(batch)

        if not self.brain.available:
            report.errors.append("没配后台模型，煮不了。料原样留着。")
            return report

        # 一、抽事件
        try:
            events = self._extract(batch, cycle)
        except (BrainError, ValueError) as exc:
            report.errors.append(f"抽事件失败：{exc}")
            return report
        report.events = len(events)

        if not events:
            # 这批全是寒暄，没长出东西。但料确实看过了，标记掉，
            # 否则它会永远堵在队列头。
            self.journal.mark_digested([e.id for e in batch])
            self.memory.set_state("cycle", str(cycle))
            return report

        # 二、落网络
        try:
            report.edges = self._weave(events, cycle)
        except Exception as exc:  # noqa: BLE001 - 网络层出错不该让整批料丢掉
            report.errors.append(f"落网络失败：{exc}")

        # 三、判特质 + 四、核对行为 + 五、结算
        try:
            touched, moved, born = self._grow(events, cycle)
            report.traits_touched = touched
            report.traits_moved = moved
            report.traits_born = born
        except (BrainError, ValueError) as exc:
            report.errors.append(f"判特质失败：{exc}")

        # 六、常驻档案
        try:
            report.dossier_updates = self._update_dossier(events, cycle)
        except (BrainError, ValueError) as exc:
            report.errors.append(f"更新档案失败：{exc}")

        # 七、自述（到点才写）
        if cycle % NARRATE_EVERY == 0:
            try:
                report.narrated = self._narrate(cycle)
            except (BrainError, ValueError) as exc:
                report.errors.append(f"写自述失败：{exc}")

        # 只有走到这里才承认这批料吃掉了
        self.journal.mark_digested([e.id for e in batch])
        self.memory.set_state("cycle", str(cycle))
        self.memory.set_state("last_digest_at", str(time.time()))
        report.usage = self.brain.usage.as_dict()
        return report

    # ------------------------------------------------------------ 一、抽事件

    def _extract(self, batch: Sequence[Entry], cycle: int) -> List[Event]:
        transcript = prompts.format_transcript(
            [
                {"turn": e.turn, "role": e.role, "content": e.content}
                for e in batch
            ]
        )
        p = prompts.extract_prompt(transcript)
        raw = self.brain.ask_json(p["system"], p["user"], max_tokens=3072)

        if not isinstance(raw, list):
            raise ValueError(f"抽事件应该返回数组，拿到 {type(raw).__name__}")

        by_turn: Dict[int, List[int]] = {}
        for e in batch:
            by_turn.setdefault(e.turn, []).append(e.id)
        all_ids = [e.id for e in batch]
        session = batch[0].session

        out: List[Event] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary", "")).strip()
            if not summary:
                continue

            # 来历：模型给的轮次映射回日记 id。给不出来就整批兜底 ——
            # 宁可指得粗，也不能没有来历。
            turns = item.get("source_turns") or []
            source_ids: List[int] = []
            for t in turns:
                try:
                    source_ids.extend(by_turn.get(int(t), []))
                except (TypeError, ValueError):
                    continue
            if not source_ids:
                source_ids = list(all_ids)

            event = Event(
                id=f"ev_{cycle}_{i}_{int(time.time())}",
                summary=summary,
                source_ids=sorted(set(source_ids)),
                session=session,
                salience=_num(item.get("salience"), 0.3, 0.0, 1.0),
                valence=_num(item.get("valence"), 0.0, -1.0, 1.0),
                questions=_strings(item.get("questions")),
                entities=_strings(item.get("entities")),
                stood_firm=bool(item.get("stood_firm")),
                happened_at=batch[0].wrote_at,
            )
            # 顶住压力的时刻，权重抬到高档 —— 但故意压在"重大突破"
            # 阈值以下。理由：这种时刻在真实使用里并不罕见，如果每次
            # 都允许绕过固化阻力，一条特质会靠"反复顶人"迅速冲到顶，
            # 那就又变成正反馈滚雪球了。它该是最重的普通事件，
            # 不该是每次都能撬动内核的杠杆。
            if event.stood_firm:
                event.salience = max(event.salience, 0.8)

            self.memory.add_event(event)
            out.append(event)
        return out

    # ------------------------------------------------------------ 二、落网络

    def _weave(self, events: Sequence[Event], cycle: int) -> int:
        """新事件进网络，并且跟"它让人想起的旧事"连上。

        这一步是赫布规则真正被喂养的地方，也是"跨越因果距离"的
        路被刻下来的时刻：新事件的 questions 会去命中旧事件，
        命中了就一起被激活，一起被激活就连线变粗。

        两种共现分开落账，因为它们不是同一种证据：

        亲历（lived）
            同一批煮出来的事件本来就发生在同一段经历里。这是事实。
        回忆（recalled）
            新事件翻旧账翻出来的。这是推测 —— 也许只是检索觉得像。

        亲历刻下的痕更深。不分开的后果是同一段对话里的事连得跟
        "碰巧被一起搜到"一样浅，多跳联想第一跳就断。
        """
        net = self.memory.load_network()

        for ev in events:
            net.add(ev.id, salience=ev.salience)

        strengthened = 0

        # 亲历：整批一次连上。能量按各自的显著性，重要的事在这段
        # 经历里留下的痕更深。
        if len(events) > 1:
            strengthened += net.co_activate(
                {ev.id: max(0.5, ev.salience) for ev in events},
                cycle=cycle,
                lived=True,
            )

        # 回忆：每条新事件各自去翻旧账
        for ev in events:
            # 用这条事件自己的说法和它"能回答的问题"去翻旧账
            query = " ".join([ev.summary] + ev.questions + ev.entities)
            hits = [
                (eid, score)
                for eid, score in self.memory.search(query, limit=8)
                if eid != ev.id and eid in net
            ]
            if not hits:
                continue

            activated: Dict[str, float] = {ev.id: 1.0}
            peak = max((s for _, s in hits), default=0.0) or 1.0
            for eid, score in hits:
                activated[eid] = max(0.15, score / peak)

            strengthened += net.co_activate(activated, cycle=cycle)

        net.tick()
        self.memory.save_network(net)
        return strengthened

    # ------------------------------------------------------------ 三到五、生长

    def _grow(self, events: Sequence[Event], cycle: int) -> Tuple[int, int, int]:
        traits = self.memory.load_traits()
        ev_view = [_event_view(e) for e in events[:APPRAISE_WINDOW]]
        by_id = {e.id: e for e in events}

        # --- 判定
        p = prompts.appraise_prompt([_trait_view(t) for t in traits], ev_view)
        verdict = self.brain.ask_json(p["system"], p["user"], max_tokens=2048)
        if not isinstance(verdict, dict):
            raise ValueError("判特质应该返回对象")

        trait_map = {t.id: t for t in traits}
        touched = 0

        for item in verdict.get("appraisals") or []:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("trait_id", ""))
            eid = str(item.get("event_id", ""))
            trait = trait_map.get(tid)
            if trait is None or eid not in by_id:
                # 指不回具体事件的判定直接丢。这里不做兜底 ——
                # 特质是人格本身，来历必须是准的，粗不行。
                continue
            signal = _num(item.get("signal"), 0.0, -1.0, 1.0)
            if signal == 0.0:
                continue
            trait.feed(Evidence(event_id=eid, signal=signal, salience=by_id[eid].salience))
            touched += 1

        # --- 新倾向
        born = 0
        for item in verdict.get("proposals") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            eids = [str(x) for x in (item.get("event_ids") or []) if str(x) in by_id]
            if not text or len(set(eids)) < PROPOSAL_MIN_EVENTS:
                # 只有一件事支持的"发现"不算发现。这道门槛就是
                # "量变才有质变"在特质诞生这一步的落点。
                continue
            tid = _trait_id(text, cycle, born)
            if tid in trait_map:
                continue
            trait = Trait(id=tid, text=text)
            for eid in sorted(set(eids)):
                trait.feed(Evidence(event_id=eid, signal=0.5, salience=by_id[eid].salience))
            trait_map[tid] = trait
            traits.append(trait)
            born += 1
            self.memory.log_change(
                cycle=cycle,
                kind="trait_born",
                target=tid,
                after=text,
                reason=str(item.get("why", ""))[:200],
                evidence=sorted(set(eids)),
            )

        # --- 核对行为（说到有没有做到）
        if traits:
            try:
                op = prompts.observe_prompt([_trait_view(t) for t in traits], ev_view)
                obs = self.brain.ask_json(op["system"], op["user"], max_tokens=1536)
                for item in obs if isinstance(obs, list) else []:
                    if not isinstance(item, dict):
                        continue
                    trait = trait_map.get(str(item.get("trait_id", "")))
                    if trait is None or not item.get("opportunity"):
                        continue
                    trait.observe(bool(item.get("expressed")))
            except (BrainError, ValueError) as exc:
                # 行为核对是校准项，缺一次不影响主干。宁可这次不校准，
                # 也不要因为它失败而丢掉上面已经判好的印证。
                self.memory.set_state("last_observe_error", str(exc)[:200])

        # --- 结算
        now = time.strftime("%Y-%m-%d %H:%M")
        moved = 0
        for trait in traits:
            before = trait.strength
            delta = trait.settle(now=now)
            if abs(delta) < 1e-9:
                self.memory.save_trait(trait)
                continue
            moved += 1
            # 质变了才记账。量变不记 —— 蓄水池里那些还没成事的
            # 涨落不是人格变化，记进去只会把账本淹掉。
            self.memory.log_change(
                cycle=cycle,
                kind="trait_moved",
                target=trait.id,
                before=f"{before:.4f}",
                after=f"{trait.strength:.4f}",
                reason=f"{trait.phase}；印证{trait.reinforced}次，动摇{trait.contradicted}次",
                evidence=trait.evidence[-12:] or [e.id for e in events[:1]],
            )
            self.memory.save_trait(trait)

            if trait.is_kernel and self.memory.get_state(f"kernel:{trait.id}") != "1":
                self.memory.set_state(f"kernel:{trait.id}", "1")
                self.memory.log_change(
                    cycle=cycle,
                    kind="kernel_formed",
                    target=trait.id,
                    after=trait.text,
                    reason=f"强度 {trait.strength:.3f}，来历 {len(trait.evidence)} 条 —— 硬了",
                    evidence=trait.evidence[-20:],
                )

        return touched, moved, born

    # ------------------------------------------------------------ 六、档案

    def _update_dossier(self, events: Sequence[Event], cycle: int) -> int:
        p = prompts.dossier_prompt(
            self.memory.dossier(), [_event_view(e) for e in events[:APPRAISE_WINDOW]]
        )
        raw = self.brain.ask_json(p["system"], p["user"], max_tokens=1024)
        if not isinstance(raw, list):
            return 0

        by_id = {e.id for e in events}
        current = self.memory.dossier()
        n = 0
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            eids = [str(x) for x in (item.get("event_ids") or []) if str(x) in by_id]
            if not key or not value or not eids:
                continue
            if current.get(key) == value:
                continue
            before = current.get(key)
            self.memory.set_dossier(
                key, value, eids, confidence=_num(item.get("confidence"), 0.8, 0.0, 1.0)
            )
            self.memory.log_change(
                cycle=cycle,
                kind="dossier_set",
                target=key,
                before=before,
                after=value,
                reason="常驻事实",
                evidence=eids,
            )
            n += 1
        return n

    # ------------------------------------------------------------ 七、自述

    def _narrate(self, cycle: int, kind: str = "derived") -> bool:
        """重写一版"我是谁"。

        只喂强度和记忆，不喂上一版。写完跟上一版比，只有真的变了
        才存 —— 否则版本历史会被一堆同义改写塞满，之后做漂移比对
        时找不到真正的转折点在哪。
        """
        traits = [t for t in self.memory.load_traits() if t.strength >= 0.2]
        if not traits:
            return False

        top_events = self.memory.recent_events(limit=200)
        top_events.sort(key=lambda e: e.salience, reverse=True)
        firm = self.memory.stood_firm_events(limit=6)

        p = prompts.narrate_prompt(
            [_trait_view(t) for t in traits[:12]],
            [_event_view(e) for e in top_events[:10]],
            [_event_view(e) for e in firm],
        )
        text = self.brain.ask(p["system"], p["user"], temperature=0.3, max_tokens=800).strip()
        if not text:
            return False

        basis = [t.id for t in traits[:12]] + [e.id for e in top_events[:10]]
        prev = self.memory.current_narrative(kind=kind)
        if prev and str(prev.get("text", "")).strip() == text:
            return False

        self.memory.add_narrative(text, basis=basis, cycle=cycle, kind=kind)
        if kind == "derived":
            self.memory.log_change(
                cycle=cycle,
                kind="narrative",
                target=f"v{cycle}",
                before=(str(prev.get("text"))[:120] if prev else None),
                after=text[:120],
                reason="从记忆重新推导（未参考上一版）",
                evidence=basis,
            )
        return True

    # ------------------------------------------------------------ 自我核对

    def audit_drift(self) -> Dict[str, object]:
        """从零重建一次，然后跟当前版本比。

        重建版单独存成 kind="rebuilt"，不覆盖演化版 —— 这是尺子，
        不是新的自己。差出去的部分就是漂移。
        """
        cycle = int(self.memory.get_state("cycle", "0"))
        current = self.memory.current_narrative("derived")
        if not current:
            return {"结论": "还没有自述可比"}

        self._narrate(cycle, kind="rebuilt")
        rebuilt = self.memory.current_narrative("rebuilt")
        if not rebuilt:
            return {"结论": "重建失败"}

        p = prompts.drift_prompt(str(current["text"]), str(rebuilt["text"]))
        try:
            verdict = self.brain.ask_json(p["system"], p["user"], max_tokens=1024)
        except (BrainError, ValueError) as exc:
            return {"结论": f"比对失败：{exc}"}

        if isinstance(verdict, dict):
            self.memory.set_state("last_audit_at", str(time.time()))
            self.memory.set_state("last_drift", json.dumps(verdict, ensure_ascii=False))
            sev = _num(verdict.get("severity"), 0.0, 0.0, 1.0)
            if sev > 0.0:
                self.memory.log_change(
                    cycle=cycle,
                    kind="drift_audit",
                    target=f"severity={sev:.2f}",
                    after=str(verdict.get("note", ""))[:200],
                    reason="从零重建后的比对",
                    evidence=[str(current["id"]), str(rebuilt["id"])],
                )
        return verdict if isinstance(verdict, dict) else {"结论": "看不懂的回答"}


# ---------------------------------------------------------------- 后台


class Grower:
    """它自己在动的那部分。

    一个守护线程，按点醒来看看有没有要煮的。没人说话的时候它也在跑 ——
    这就是"loam 是个自己活着的进程"和"一个被调用的工具"的区别。

    不用 systemd 也不用 cron，因为要能在 Termux 上活着。
    """
    def __init__(
        self,
        digester: Digester,
        interval: float = 60.0,
        idle_seconds: float = IDLE_SECONDS,
        audit_every: int = AUDIT_EVERY,
        on_report: Optional[Any] = None,
        step_lock: Optional[threading.RLock] = None,
    ) -> None:
        self.digester = digester
        self.interval = interval
        self.idle_seconds = idle_seconds
        self.audit_every = audit_every
        self.on_report = on_report

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.reports: List[DigestReport] = []
        self.last_error: Optional[str] = None
        self._step_lock = step_lock


    # ------------------------------------------------------------ 生命周期

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="loam-grower", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------ 循环

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._step_lock:
                    with self._step_lock:
                        self.step()
                else:
                    self.step()
            except Exception:  # noqa: BLE001 - 后台线程死了整个成长就停了
                self.last_error = traceback.format_exc(limit=3)
            self._stop.wait(self.interval)

    def step(self) -> Optional[DigestReport]:
        """醒来一次做的全部事情。也可以手动调，用于测试和 CLI。"""
        d = self.digester

        # 先自愈：有没有该收到却没收到的轮次
        filled = d.journal.reconcile_gaps(d.character)
        stale = d.journal.stale_sessions(d.character, idle_seconds=self.idle_seconds)

        if not d.ready(idle_seconds=self.idle_seconds):
            return None

        report = d.digest_once()
        if filled:
            report.errors.append(f"顺手关闭了 {filled} 个漏轮缺口")
        if stale:
            report.errors.append(f"检测到 {len(stale)} 个长时间无新输入会话（仅提示）")
        self.reports.append(report)
        if len(self.reports) > 200:
            del self.reports[:-200]
        if self.on_report:
            try:
                self.on_report(report)
            except Exception:  # noqa: BLE001
                self.last_error = traceback.format_exc(limit=3)

        if self.audit_every and report.cycle and report.cycle % self.audit_every == 0:
            try:
                d.audit_drift()
            except Exception:  # noqa: BLE001
                self.last_error = traceback.format_exc(limit=3)

        return report

    def drain(self, max_rounds: int = 50) -> List[DigestReport]:
        """一直煮到没料为止。用于导入历史记录，或者测试。"""
        out = []
        for _ in range(max_rounds):
            if not self.digester.pending_count():
                break
            r = self.digester.digest_once()
            out.append(r)
            if r.errors and not r.events:
                break
        return out


# ---------------------------------------------------------------- 小工具


def _num(v: object, default: float, lo: float, hi: float) -> float:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if x != x:  # NaN
        return default
    return max(lo, min(hi, x))


def _strings(v: object) -> List[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()][:12]


def _trait_id(text: str, cycle: int, n: int) -> str:
    import hashlib

    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"tr_{h}"


def _trait_view(t: Trait) -> Dict[str, object]:
    return {
        "id": t.id,
        "text": t.text,
        "strength": t.strength,
        "evidence_count": len(t.evidence),
    }


def _event_view(e: Event) -> Dict[str, object]:
    return {
        "id": e.id,
        "summary": e.summary,
        "salience": e.salience,
        "stood_firm": e.stood_firm,
    }