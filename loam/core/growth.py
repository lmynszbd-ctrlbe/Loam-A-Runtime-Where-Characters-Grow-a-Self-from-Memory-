"""特质强度的内生生长规律。

这里没有外部限速器。一条特质变化得多快，由它自己当前所处的位置决定：

    萌芽期（强度低）  —— 很软，一次经历能推动不少
    生长期（强度中）  —— 变化最快，已经立住但还没定型
    固化期（强度高）  —— 很硬，怎么推都只动一点

这样带来两个后果：
1. "慢"是系统自己的性质，不是被谁按住的。
2. 内核不需要预先写死。长久积累后自己变硬的那几条，就是内核。
   它是长出来的，不是给的。

灵感注记（仅作理解辅助，不参与计算）：
    可把“道生一，一生二，二生三，三生万物”理解为
    从萌芽变量到层级结构逐步涌现的过程。

另外有两个机制配合：

迟滞（hysteresis）
    经历不直接改动特质，先进蓄水池。攒过一个位置才真的动。
    中间那些没到线的，就是量变。

表达反馈（expression feedback）
    如果某条特质的实际表现频率远高于它的强度，说明过冲了，自动回压。
    这是"雪球滚不起来"的原因 —— 越滚越滚不动，而且滚过头会被拉回来。
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------- 常量

#: 基础可塑率。整个系统的"时间快慢"总旋钮。
PLASTICITY = 0.35

#: 萌芽下限。让强度为 0 的新特质也能起步，否则 S*(1-S) 在 0 处永远不动。
SEED_FLOOR = 0.06

#: 强度上限。永远留一点余地，不允许任何特质变成绝对。
CEILING = 0.97

#: 突破阈值。单次证据强度超过这个值，可以绕过固化阻力。
#: 对应"一件极其重大的事能一次改变一个人"。
BREAKTHROUGH = 0.85

#: 突破时额外获得的推动力系数。
BREAKTHROUGH_GAIN = 0.5

#: 蓄水池阈值相对于当前可塑量的比例。
#: 用比例而不是绝对值，是为了保证阈值永远够得着：一条已经很硬的特质
#: 可塑量小，它的阈值也跟着小，所以它仍然可以被长期的持续动摇改变 ——
#: 只是需要攒很久。绝对阈值会让高强度特质变成永远无法撼动的死结。
GATE_RATIO = 0.5

#: 蓄水池阈值下限。防止萌芽期的特质因为阈值趋零而抖动。
GATE_FLOOR = 0.004

#: 动态门槛增益。每发生一次"质变提交"，下一次提交阈值按该倍率抬高。
#: 用来实现边际递减：越往后，越难继续大幅跃迁。
GATE_LEVEL_MULTIPLIER = 1.1

#: 动态门槛的最大放大倍数。防止阈值无限上升导致完全冻结。
GATE_LEVEL_CAP = 1.5

#: 质变提交后保留的 pending 比例（惯性残留）。
#: 不是把经历抹平，而是给下一轮一点连续性。
PENDING_RESIDUAL = 0.2

#: 蓄水池的渗漏系数。只在完全没有输入的周期生效 ——
#: 渗漏的意思是"长期不被印证的冲动自己淡掉"，不是"攒着的东西一律漏"。
#:
#: 这个区分很要紧。如果每个周期都漏，蓄水池就有了一个天花板
#: （delta / (1 - LEAK)），力度低于某个值的证据永远攒不过阈值 ——
#: 无论重复多少次都不算。那等于说"小事再多也不构成人"，
#: 跟"慢慢长出来"正好相反。水滴要能穿石，只是要很久。
LEAK = 0.90

#: 行为校准系数。控制"强度向实际表现频率靠拢"的速度。
CALIBRATION = 0.12

#: 行为校准的容差。表现频率和强度差在此范围内视为一致，不做校准。
CALIBRATION_TOLERANCE = 0.15

#: 强度本身的极缓慢衰减（每个完全无输入的周期）。
DECAY = 0.999

#: 快态衰减。快态像心电图，会先响应，再逐渐回到稳态附近。
FAST_DECAY = 0.72

#: 快态最大偏移，防止一件事把表层反应推到失控。
FAST_LIMIT = 0.28

#: 低于该置信度的解释只进入待确认池，不进入长期蓄水池。
UNCERTAINTY_GATE = 0.55

#: 默认多少个无输入周期后进入蛰伏。
DORMANCY_AFTER = 24

#: 质变越接近边界，实际吸收越弱；硬边界仍由 CEILING 兜底。
SATURATION_START = 0.88

#: 回弹力。极端特质长期无输入时，自然向中心 0.5 缓慢回归。
#: 不是"遗忘"，而是"没有持续印证时，极端立场会慢慢软化"。
#: 公式：回弹量 = REBOUND * (|S-0.5|/0.5) * sign(S-0.5)，方向向中心。
REBOUND = 0.001

#: 冻结阈值。超过此周期的完全无输入，特质进入冻结态：不吸收、不衰减、
#: 不回弹，像冰封一样保留原样。唤醒后恢复活跃。
FREEZE_AFTER = 48

#: 自主微调。蛰伏/收敛态无输入时，极小的自发漂移，模拟"无事时也会
#: 自己想一想"。方向随机，幅度极小，相当于"梦里的微调"。
AUTONOMOUS_DRIFT = 0.0002


# ---------------------------------------------------------------- 数据结构


@dataclass
class Evidence:
    """一次推动特质的经历。

    Attributes:
        event_id: 指向原始事件。任何强度变化都必须能指回具体哪件事，
            这是防漂移的根本手段，所以此字段不允许为空。
        signal: 方向与力度，取值 [-1, 1]。正为印证，负为动摇。
        salience: 这件事本身有多重大，取值 [0, 1]。
    """

    event_id: str
    signal: float
    salience: float = 0.5
    #: 对“当前解释是否可靠”的认识论置信度，不等于事实真伪。
    confidence: float = 1.0
    #: 字面与真实意图可能不一致的程度。系统不读心，只降低承诺。
    ambiguity: float = 0.0

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("证据必须指向一个具体事件（event_id 不可为空）")
        self.signal = _clamp(self.signal, -1.0, 1.0)
        self.salience = _clamp(self.salience, 0.0, 1.0)
        self.confidence = _clamp(self.confidence, 0.0, 1.0)
        self.ambiguity = _clamp(self.ambiguity, 0.0, 1.0)

    @property
    def force(self) -> float:
        """有效推力：重要度之外，还受解释置信度与歧义抑制。"""
        epistemic = self.confidence * (1.0 - 0.65 * self.ambiguity)
        return self.signal * self.salience * epistemic


@dataclass
class Trait:
    """一条"我觉得"。

    人格不存放在这里 —— 这只是一个强度数字加一串来历。
    真正的人格是这些强度在检索时造成的偏向。
    """

    id: str
    text: str
    strength: float = 0.0
    #: 蓄水池。未提交的变化在这里攒着。
    pending: float = 0.0

    #: 动态门槛等级。每发生一次质变就提升一级，使下一次更难。
    gate_level: int = 0

    #: 快态与惯性：先在表层起波动，长期稳态仍由 strength 表示。
    transient: float = 0.0
    momentum: float = 0.0

    #: 生命周期与人格暖启动。
    inactive_cycles: int = 0
    warmup_remaining: int = 0
    from_seed: bool = False

    #: 运行期调节项（由 runtime config 注入，不需要成为历史真值）。
    fuzziness: float = 0.0
    uncertainty_gate: float = UNCERTAINTY_GATE
    dormancy_after: int = DORMANCY_AFTER

    #: 来历。每个提交过的变化都留下它依据的事件。
    evidence: List[str] = field(default_factory=list)

    reinforced: int = 0
    contradicted: int = 0

    #: 实际被表现出来的次数 / 有机会被表现的次数，用于表达反馈。
    expressed: int = 0
    opportunities: int = 0

    formed_at: Optional[str] = None
    last_commit_at: Optional[str] = None

    # ------------------------------------------------------------ 生长

    @property
    def gate(self) -> float:
        """当前蓄水池阈值 —— 需要攒多少才会发生一次质变。

        由两部分共同决定：
        1) 基础门槛：跟当前可塑量成比例。
        2) 等级放大：每次质变后下一次门槛更高（边际递减）。

        这样既保留"生长期快、固化期慢"，又避免连续质变过快把角色
        推成不自然的超级状态。
        """
        base = max(GATE_FLOOR, GATE_RATIO * self._capacity())
        level = max(0, int(self.gate_level))
        scale = min(GATE_LEVEL_CAP, math.pow(GATE_LEVEL_MULTIPLIER, level))
        return base * scale

    def _capacity(self) -> float:
        """当前的可塑量，一个 S*(1-S) 钟形。

        萌芽期软但基数小，生长期最快，固化期几乎推不动。
        向上向下用同一个值 —— 顽固是对称的：既难以再往上，
        也难以被压下去。

        要撼动一条已经固化的特质只有两条路：一次极重大的事件
        （见 BREAKTHROUGH），或者足够长时间的持续动摇。跟人一样。
        """
        s = max(self.strength, SEED_FLOOR)
        room = max(CEILING - self.strength, SEED_FLOOR)
        return s * room

    def feed(self, ev: Evidence) -> None:
        """吸收一次经历：先起快态，再过认识论内门，最后进入长期蓄水池。

        高歧义/低置信度并不会被当成“反话真相”。它只留下暂态反应并
        进入待确认池；之后出现同方向、较可靠的独立经历时才折价吸收。
        """
        jitter = _stable_jitter(self.id, ev.event_id, self.fuzziness)
        force = ev.force * jitter
        delta = PLASTICITY * self._capacity() * force

        # 极重大的事件可以绕过固化阻力，但仍受解释置信度约束。
        if ev.salience >= BREAKTHROUGH:
            delta += (
                BREAKTHROUGH_GAIN
                * ev.signal
                * (ev.salience - BREAKTHROUGH)
                * ev.confidence
                * (1.0 - 0.65 * ev.ambiguity)
            )

        # 快态不等于人格提交：它允许短期不认同、犹疑、回摆。
        self.transient = _clamp(self.transient + delta * 1.35, -FAST_LIMIT, FAST_LIMIT)
        self.momentum = _clamp(self.momentum * 0.68 + force * 0.32, -1.0, 1.0)

        # 冻结态：只记录经历、更新快态，完全不写入长期蓄水池。
        # 必须在 inactive_cycles 重置之前检查，否则冻结会被误解除。
        if self.life_phase == "冻结":
            if force >= 0:
                self.reinforced += 1
            else:
                self.contradicted += 1
            if ev.event_id not in self._staged:
                self._staged.append(ev.event_id)
            return

        self._fed = True
        self.inactive_cycles = 0

        epistemic = ev.confidence * (1.0 - ev.ambiguity)
        if epistemic < self.uncertainty_gate:
            self._uncertain.append(
                {
                    "event_id": ev.event_id,
                    "signal": ev.signal,
                    "salience": ev.salience,
                    "confidence": ev.confidence,
                    "ambiguity": ev.ambiguity,
                }
            )
            self._uncertain = self._uncertain[-32:]
            return

        # 较可靠的新经历可确认同方向的旧疑点；旧疑点只折价进入长期层。
        promoted = 0.0
        kept: List[Dict[str, object]] = []
        for old in self._uncertain:
            old_signal = float(old.get("signal", 0.0) or 0.0)
            if old_signal * ev.signal > 0.0 and str(old.get("event_id", "")) != ev.event_id:
                old_force = (
                    old_signal
                    * float(old.get("salience", 0.0) or 0.0)
                    * float(old.get("confidence", 0.0) or 0.0)
                    * (1.0 - float(old.get("ambiguity", 0.0) or 0.0))
                )
                promoted += PLASTICITY * self._capacity() * old_force * 0.35
                old_id = str(old.get("event_id", ""))
                if old_id and old_id not in self._staged:
                    self._staged.append(old_id)
            else:
                kept.append(old)
        self._uncertain = kept

        # 角色卡种子处于暖启动：快态照常响应，写入长期人格则更谨慎。
        assimilation = 0.62 if self.warmup_remaining > 0 else 1.0
        if self.life_phase == "蛰伏":
            assimilation *= 0.35
        elif self.life_phase == "复苏":
            assimilation *= 0.68

        # 吸收饱和：近边界时同向吸收打折，提前消耗而非硬拦。
        if (delta > 0.0 and self.strength > SATURATION_START) or (
            delta < 0.0 and self.strength < (1.0 - SATURATION_START)
        ):
            edge = max(self.strength, 1.0 - self.strength)
            feed_resistance = _clamp(1.0 - (edge - SATURATION_START) / 0.18, 0.25, 1.0)
            delta *= feed_resistance

        self.pending += (delta + promoted) * assimilation

        if force >= 0:
            self.reinforced += 1
        else:
            self.contradicted += 1
        if ev.event_id not in self._staged:
            self._staged.append(ev.event_id)

    def absorb_relation(self, amount: float, event_id: str) -> None:
        """吸收一跳特质关系传播；只进快态/蓄水池，不在同轮级联提交。"""
        if not event_id or abs(amount) < 1e-12:
            return
        amount = _clamp(amount, -0.12, 0.12)
        self.transient = _clamp(self.transient + amount, -FAST_LIMIT, FAST_LIMIT)
        self.pending += amount
        self.momentum = _clamp(self.momentum * 0.8 + math.copysign(0.2, amount), -1.0, 1.0)
        self._fed = True
        self.inactive_cycles = 0
        if event_id not in self._staged:
            self._staged.append(event_id)

    #: 尚未提交的证据 id。跨周期保留 —— 蓄水池里攒着的每一分变化
    #: 都必须能指回它的来历，所以未提交前不允许丢弃。
    _staged: List[str] = field(default_factory=list, repr=False)

    #: 解释不确定、尚未获独立印证的证据。
    _uncertain: List[Dict[str, object]] = field(default_factory=list, repr=False)

    #: 本周期是否有经历进来。
    _fed: bool = field(default=False, repr=False)

    def settle(self, now: Optional[str] = None) -> float:
        """结算一个周期。

        Returns:
            实际发生的强度变化量。0 表示这个周期只是量变。
        """
        had_input, self._fed = self._fed, False

        if had_input:
            self.inactive_cycles = 0
            if self.warmup_remaining > 0:
                self.warmup_remaining -= 1
        else:
            self.inactive_cycles += 1

        # 快态会回落，惯性更慢；因此可有小波折，但不会取代稳态人格。
        self.transient *= FAST_DECAY if had_input else 0.82
        self.momentum *= 0.86 if had_input else 0.72

        # 行为校准：让强度向实际表现频率靠拢
        self.pending += self._calibration()

        moved = 0.0
        if abs(self.pending) >= self.gate:
            before = self.strength
            applied = self.pending * (1.0 - PENDING_RESIDUAL)
            # 物极必反的软饱和：接近两端时继续同向会越来越难。
            if (applied > 0.0 and self.strength > SATURATION_START) or (
                applied < 0.0 and self.strength < (CEILING - SATURATION_START)
            ):
                edge = max(self.strength, CEILING - self.strength)
                resistance = _clamp(1.0 - (edge - SATURATION_START) / 0.18, 0.15, 1.0)
                applied *= resistance
            self.strength = _clamp(self.strength + applied, 0.0, CEILING)
            moved = self.strength - before
            # 质变发生，把攒到现在的全部来历记进去
            self.evidence.extend(self._staged)
            self._staged.clear()
            self.last_commit_at = now
            if self.formed_at is None:
                self.formed_at = now
            # 不完全清零：保留一部分惯性，避免刚跃迁完立刻掉回去。
            self.pending *= PENDING_RESIDUAL
            if abs(moved) > 1e-9:
                self.gate_level += 1
            # 到边界后，同向残留不再保留，避免在边界上空转。
            if (self.strength <= 0.0 and self.pending < 0.0) or (
                self.strength >= CEILING and self.pending > 0.0
            ):
                self.pending = 0.0
        elif not had_input:
            # 这个周期没人提它 —— 蓄水池渗漏一部分。
            # 有输入的周期不漏：一次次被印证的小事必须能攒起来，
            # 否则弱信号永远够不到阈值，"量变到质变"就断在了半路。
            self.pending *= LEAK

        # 冻结态：不衰减、不回弹、不自主微调，完全冰封。
        if not had_input and self.life_phase == "冻结":
            pass  # 冻结态什么都不做，强度不变
        elif not had_input:
            # 蛰伏/收敛态：微小的自主漂移，相当于"无事时自己想一想"。
            if self.life_phase in ("蛰伏", "收敛"):
                drift = AUTONOMOUS_DRIFT * (1.0 - 2.0 * (hash(self.id + str(self.inactive_cycles)) % 10000) / 10000.0)
                self.strength = _clamp(self.strength + drift, 0.0, CEILING)
            self.strength *= DECAY
            # 回弹：极端特质无输入时自然向中心 0.5 软化。
            if abs(self.strength - 0.5) > 0.25:
                rebound = REBOUND * (abs(self.strength - 0.5) / 0.5) * (self.strength - 0.5)
                self.strength = _clamp(self.strength - rebound, 0.0, CEILING)
        return moved

    def _calibration(self) -> float:
        """让强度向实际行为频率靠拢，双向。

        强度虚高（说自己勇敢却从不勇敢）—— 往下拉。
        强度虚低（口口声声不在意却每次都在意）—— 往上推。

        这一条是"人格必须兑现在行为里"的机制保证：一条特质无法
        只靠反复被谈论就长大，它得真的表现出来。反过来，一条
        持续表现出来的倾向也无法被自我描述压住。

        萌芽期不校准 —— 那时候频繁表现正是它在长出来的证据。
        """
        if self.opportunities < 8 or self.strength < 0.25:
            return 0.0
        rate = self.expressed / self.opportunities
        gap = rate - self.strength
        if abs(gap) < CALIBRATION_TOLERANCE:
            return 0.0
        excess = gap - math.copysign(CALIBRATION_TOLERANCE, gap)
        return CALIBRATION * excess * self._capacity()

    def observe(self, expressed: bool) -> None:
        """记录一次"有机会表现这条特质"的场合及其结果。"""
        self.opportunities += 1
        if expressed:
            self.expressed += 1

    # ------------------------------------------------------------ 状态

    @property
    def effective_strength(self) -> float:
        """对话时可见的瞬时倾向；稳态不被短期波动直接覆盖。"""
        return _clamp(self.strength + self.transient, 0.0, CEILING)

    @property
    def life_phase(self) -> str:
        """生命周期：暖启动、活跃、收敛、蛰伏、冻结、复苏。"""
        if self.warmup_remaining > 0:
            return "暖启动"
        if self.inactive_cycles >= max(1, int(FREEZE_AFTER)):
            return "冻结"
        if self.inactive_cycles >= max(1, int(self.dormancy_after)):
            return "蛰伏"
        if self.inactive_cycles >= max(1, int(self.dormancy_after) // 2):
            return "收敛"
        if self.inactive_cycles > 0 and abs(self.transient) > 0.015:
            return "复苏"
        return "活跃"

    @property
    def phase(self) -> str:
        """长期强度所处阶段，仅用于人看。"""
        if self.strength < 0.25:
            return "萌芽"
        if self.strength < 0.65:
            return "生长"
        if self.strength < 0.85:
            return "定型"
        return "固化"

    @property
    def is_kernel(self) -> bool:
        """是否已经硬到可以算内核。

        注意这不是谁授予的身份，只是"长得够久够实"的自然结果。
        """
        return self.strength >= 0.85 and len(self.evidence) >= 20


# ---------------------------------------------------------------- 工具


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def half_life_to_decay(half_life_cycles: float) -> float:
    """把"多少周期衰减一半"换算成每周期的衰减系数。"""
    if half_life_cycles <= 0:
        raise ValueError("半衰期必须为正")
    return math.pow(0.5, 1.0 / half_life_cycles)


def _stable_jitter(trait_id: str, event_id: str, fuzziness: float) -> float:
    """稳定扰动：同一 trait+event 在不同重跑里得到同一个微扰系数。

    目的不是掷骰子，而是让曲线脱离“机械直线”；同时保持可复现，
    避免同一份原始证据每次重算都长成不一样的人。
    """
    span = _clamp(float(fuzziness or 0.0), 0.0, 0.45)
    if span <= 1e-12:
        return 1.0

    raw = f"{trait_id}\x00{event_id}".encode("utf-8")
    h = hashlib.sha256(raw).digest()
    u = int.from_bytes(h[:8], "big") / float((1 << 64) - 1)
    signed = (u * 2.0) - 1.0  # [-1, 1]
    return _clamp(1.0 + signed * span, 1.0 - span, 1.0 + span)

