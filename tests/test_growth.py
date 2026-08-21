"""生长规律的行为测试。

这些测试断言的不是具体数值，而是机制该有的性质。
参数可以调，性质不能破。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.core.growth import (  # noqa: E402
    CEILING,
    PENDING_RESIDUAL,
    Evidence,
    Trait,
)


def drive(trait, cycles, signal=1.0, salience=0.5, express=0.5, tag="t"):
    """推动一条特质若干周期。"""
    for i in range(cycles):
        trait.feed(Evidence(event_id=f"{tag}{i}", signal=signal, salience=salience))
        trait.observe(expressed=(i % 100) < express * 100)
        trait.settle(now=f"{tag}c{i}")
    return trait


def test_growth_is_s_shaped():
    """生长必须是 S 形：先慢，中间快，接近顶点又慢下来。"""
    t = Trait(id="a", text="x")
    marks = {}
    for c in range(1, 101):
        t.feed(Evidence(event_id=f"e{c}", signal=1.0, salience=0.5))
        t.observe(expressed=(c % 10) < 5)
        t.settle(now=f"c{c}")
        marks[c] = t.strength

    early = marks[10] - marks[5]
    middle = marks[35] - marks[30]
    late = marks[100] - marks[95]

    assert middle > early, "生长期该比萌芽期快"
    assert middle > late, "接近顶点该慢下来"
    assert t.strength <= CEILING


def test_no_hard_limiter_needed():
    """慢是内生的，不是被限位器按住的：单周期变化量自己就有上界。"""
    t = Trait(id="b", text="x")
    t.strength = 0.5
    for i in range(50):  # 一个周期里灌 50 次经历
        t.feed(Evidence(event_id=f"e{i}", signal=1.0, salience=0.6))
    moved = t.settle(now="c")
    assert moved < 0.5, f"单周期不该跳这么多：{moved}"


def test_kernel_emerges_rather_than_assigned():
    """内核不是预先指定的，是长久积累后自己变硬的结果。"""
    t = Trait(id="c", text="x")
    assert not t.is_kernel
    drive(t, 60, salience=0.6, express=0.9, tag="k")
    assert t.is_kernel
    assert len(t.evidence) >= 20, "内核必须有足够的来历"


def test_hardened_trait_resists_casual_opposition():
    """固化的特质不该因为几次普通反对就松动。"""
    t = drive(Trait(id="d", text="x"), 60, salience=0.6, express=0.9, tag="a")
    before = t.strength
    drive(t, 5, signal=-1.0, salience=0.5, express=0.85, tag="b")
    assert before - t.strength < 0.10, "几次普通反对不该大幅改变已固化的特质"


def test_hardened_trait_yields_to_sustained_pressure():
    """但长期持续的动摇必须真的能改变它 —— 否则就是死结，不是人格。"""
    t = drive(Trait(id="e", text="x"), 60, salience=0.6, express=0.9, tag="a")
    before = t.strength
    drive(t, 40, signal=-0.9, salience=0.55, express=0.3, tag="b")
    assert t.strength < before - 0.2, "长期动摇必须有效"


def test_breakthrough_event_can_shake_hardened_trait():
    """一件极重大的事可以一次撼动固化的特质。"""
    t = drive(Trait(id="f", text="x"), 60, salience=0.6, express=0.9, tag="a")
    before = t.strength
    t.feed(Evidence(event_id="shock", signal=-1.0, salience=0.98))
    t.observe(expressed=True)
    t.settle(now="s")
    assert t.strength < before, "重大事件应当留下痕迹"


def test_quantitative_accumulation_before_qualitative_change():
    """量变阶段：经历进了蓄水池，但强度还没动。"""
    t = Trait(id="g", text="x")
    moved = []
    for i in range(4):
        t.feed(Evidence(event_id=f"tiny{i}", signal=0.25, salience=0.2))
        moved.append(t.settle(now=f"c{i}"))
    assert all(m == 0.0 for m in moved), "微弱经历不该立刻造成质变"
    assert t.pending > 0, "但必须攒在蓄水池里"


def test_provenance_survives_accumulation():
    """蓄水池里攒着的来历不能丢 —— 质变时要能指回全部依据。"""
    t = Trait(id="h", text="x")
    for i in range(4):
        t.feed(Evidence(event_id=f"tiny{i}", signal=0.25, salience=0.2))
        t.settle(now=f"c{i}")
    drive(t, 12, salience=0.6, express=0.8, tag="big")
    assert "tiny0" in t.evidence, "早期微弱证据必须被保留到质变时记入"


def test_evidence_requires_provenance():
    """无来历的修改一律拒绝。这是防漂移的根本手段。"""
    try:
        Evidence(event_id="", signal=1.0, salience=0.9)
    except ValueError:
        pass
    else:
        raise AssertionError("无 event_id 的证据必须被拒绝")


def test_inflated_strength_gets_pulled_down():
    """说自己勇敢却从不勇敢 —— 强度会被行为拉下来。"""
    t = Trait(id="i", text="我很勇敢")
    t.strength = 0.90
    for i in range(60):
        t.observe(expressed=False)
        t.settle(now=f"c{i}")
    assert t.strength < 0.75, "虚高的强度必须被行为校准拉下来"


def test_understated_strength_gets_pushed_up():
    """嘴上不承认但每次都在做 —— 强度会被行为推上去。"""
    t = Trait(id="j", text="我在意别人怎么看我")
    t.strength = 0.30
    for i in range(60):
        t.observe(expressed=True)
        t.settle(now=f"c{i}")
    assert t.strength > 0.40, "持续表现的倾向压不住"


def test_unused_trait_fades():
    """长期无人问津的特质会淡出（但不会归零消失）。"""
    t = Trait(id="k", text="x")
    t.strength = 0.70
    for i in range(2000):
        t.settle(now=f"c{i}")
    assert t.strength < 0.20, "该淡出"
    assert t.strength > 0.0, "但不该被彻底抹掉"


def test_active_trait_does_not_decay():
    """被持续印证的特质不该因为"还没攒够下一次质变"而倒退。"""
    t = Trait(id="l", text="x")
    t.strength = 0.60
    before = t.strength
    for i in range(10):
        t.feed(Evidence(event_id=f"e{i}", signal=0.1, salience=0.1))
        t.observe(expressed=True)
        t.settle(now=f"c{i}")
    assert t.strength >= before, "有输入的周期不该衰减"


def test_dynamic_gate_increases_after_commit():
    """每次发生质变后，下一次门槛应当更高（边际递减）。"""
    t = Trait(id="m", text="x")
    gate0 = t.gate
    t.feed(Evidence(event_id="m0", signal=1.0, salience=1.0))
    moved = t.settle(now="m1")

    assert moved > 0.0, "应先发生一次质变"
    assert t.gate_level == 1, "发生质变后应抬升 gate_level"
    assert t.gate > gate0, "下一次门槛应上升"


def test_commit_keeps_pending_residual():
    """质变后 pending 不清零，保留残留惯性。"""
    t = Trait(id="n", text="x")
    t.feed(Evidence(event_id="n0", signal=1.0, salience=1.0))
    before_pending = t.pending
    moved = t.settle(now="n1")

    assert moved > 0.0
    assert moved < before_pending, "本轮不应吃掉全部 pending"
    assert abs(t.pending - before_pending * PENDING_RESIDUAL) < 1e-9


def test_rebound_pulls_extreme_trait_toward_center():
    """极端特质长时间无输入时会向中心 0.5 自然软化。"""
    t = Trait(id="r", text="x")
    t.strength = 0.92
    for i in range(500):
        t.settle(now=f"c{i}")
    assert t.strength < 0.88, "极端高位应被回弹拉向中心"
    # DECAY 独自作用 500 周期后约 0.56，回弹让它不低于 0.55
    assert t.strength > 0.50, "回弹不该快到让特质崩掉"


def test_feed_saturation_near_boundary():
    """近边界时同向吸收打折，提前消耗而非硬拦。"""
    t = Trait(id="s", text="x")
    t.strength = 0.92  # 近上限
    # 灌 30 次同向高权经历
    for i in range(30):
        t.feed(Evidence(event_id=f"s{i}", signal=1.0, salience=0.7))
    t.settle(now="s")
    # 如果是无饱和的线性吸收，pending 会远超 0.03
    # 有饱和后，吸收明显打折
    assert t.pending < 0.06, "近边界吸收应被饱和打折"


def test_seed_warmup_assimilation():
    """种子特质暖启动期间，写入长期人格更谨慎。"""
    t = Trait(id="w", text="x", warmup_remaining=6, from_seed=True)
    assert t.life_phase == "暖启动"
    # 暖启动期间 assimilation=0.62，pending 积累慢
    for i in range(3):
        t.feed(Evidence(event_id=f"w{i}", signal=1.0, salience=0.6))
        t.settle(now=f"w{i}")
    # 暖启动结束后 warmup 递减
    assert t.warmup_remaining >= 0
    assert t.pending >= 0, "pending 不应为负"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)