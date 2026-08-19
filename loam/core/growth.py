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

import math
from dataclasses import dataclass, field
from typing import List, Optional

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

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("证据必须指向一个具体事件（event_id 不可为空）")
        self.signal = _clamp(self.signal, -1.0, 1.0)
        self.salience = _clamp(self.salience, 0.0, 1.0)

    @property
    def force(self) -> float:
        """这次经历的有效推力。"""
        return self.signal * self.salience


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

        跟当前可塑量成比例。所以高强度特质的阈值也小，
        它仍然可以被改变，只是每次只动一点，而且要攒很久。
        """
        return max(GATE_FLOOR, GATE_RATIO * self._capacity())

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
        """吸收一次经历。只进蓄水池，不直接改强度。"""
        force = ev.force
        delta = PLASTICITY * self._capacity() * force

        # 极重大的事件可以绕过固化阻力
        if ev.salience >= BREAKTHROUGH:
            delta += BREAKTHROUGH_GAIN * ev.signal * (ev.salience - BREAKTHROUGH)

        self.pending += delta
        if force >= 0:
            self.reinforced += 1
        else:
            self.contradicted += 1
        self._staged.append(ev.event_id)
        self._fed = True

    #: 尚未提交的证据 id。跨周期保留 —— 蓄水池里攒着的每一分变化
    #: 都必须能指回它的来历，所以未提交前不允许丢弃。
    _staged: List[str] = field(default_factory=list, repr=False)

    #: 本周期是否有经历进来。
    _fed: bool = field(default=False, repr=False)

    def settle(self, now: Optional[str] = None) -> float:
        """结算一个周期。

        Returns:
            实际发生的强度变化量。0 表示这个周期只是量变。
        """
        had_input, self._fed = self._fed, False

        # 行为校准：让强度向实际表现频率靠拢
        self.pending += self._calibration()

        moved = 0.0
        if abs(self.pending) >= self.gate:
            before = self.strength
            self.strength = _clamp(self.strength + self.pending, 0.0, CEILING)
            moved = self.strength - before
            # 质变发生，把攒到现在的全部来历记进去
            self.evidence.extend(self._staged)
            self._staged.clear()
            self.last_commit_at = now
            if self.formed_at is None:
                self.formed_at = now
            self.pending = 0.0
        elif not had_input:
            # 这个周期没人提它 —— 蓄水池渗漏一部分。
            # 有输入的周期不漏：一次次被印证的小事必须能攒起来，
            # 否则弱信号永远够不到阈值，"量变到质变"就断在了半路。
            self.pending *= LEAK

        # 只有完全没被激活的周期才衰减。
        # 被持续印证的特质不该因为"还没攒够下一次质变"而倒退。
        if not had_input:
            self.strength *= DECAY
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
    def phase(self) -> str:
        """当前所处阶段，仅用于人看。"""
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
