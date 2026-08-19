"""赫布记忆网络的行为测试。

断言的是机制该有的性质，不是具体数值。参数可以调，性质不能破。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loam.core.network import Network, seed_from_matches  # noqa: E402


def chain_network(rounds=15):
    """建一张"紧张 → 汇报 → 被打断 → 脑子空了"的链式网络。

    注意 ep_panic 跟 ep_nervous 从未一起出现过，也不在语义上相近。
    它只能靠网络自己长出的路径被找到。
    """
    net = Network()
    for nid, sal in [
        ("ep_nervous", 0.5),
        ("ep_report", 0.6),
        ("ep_boss", 0.8),
        ("ep_panic", 0.9),
        ("ep_lunch", 0.1),
        ("ep_weather", 0.1),
        ("ep_cat", 0.2),
    ]:
        net.add(nid, salience=sal)
    for _ in range(rounds):
        net.co_activate({"ep_nervous": 1.0, "ep_report": 0.8})
        net.co_activate({"ep_report": 1.0, "ep_boss": 0.9})
        net.co_activate({"ep_boss": 1.0, "ep_panic": 0.9})
        net.co_activate({"ep_lunch": 1.0, "ep_weather": 0.5})
        net.tick()
    return net


def test_coactivation_creates_edges():
    """一起被想起的，连接就变强 —— 这是唯一的学习规则。"""
    net = chain_network()
    assert net.weight("ep_nervous", "ep_report") > 0.1
    assert net.weight("ep_report", "ep_boss") > 0.1


def test_never_coactivated_stays_unconnected():
    """从未一起出现过的东西之间不该有连线。"""
    net = chain_network()
    assert net.weight("ep_nervous", "ep_panic") == 0.0
    assert net.weight("ep_report", "ep_cat") == 0.0


def test_multi_hop_association():
    """联想必须能跳多步。

    这是"只跳一步就停了"那个坑的直接修复：ep_panic 距离起点 3 跳，
    跟起点既不字面相似也不语义相似，只能靠路径找到。
    """
    net = chain_network()
    found = {nid for nid, _ in net.spread({"ep_nervous": 1.0}, limit=10)}
    assert "ep_panic" in found, "3 跳外的因果相关记忆必须能被找到"


def test_energy_decays_with_distance():
    """越远的记忆激活越弱 —— 联想有梯度，不是全有或全无。"""
    net = chain_network()
    scores = dict(net.spread({"ep_nervous": 1.0}, limit=10))
    assert scores["ep_report"] > scores["ep_boss"] > scores["ep_panic"]


def test_unrelated_memories_not_activated():
    """无关的记忆不该被带出来。"""
    net = chain_network()
    found = {nid for nid, _ in net.spread({"ep_nervous": 1.0}, limit=10)}
    assert "ep_lunch" not in found
    assert "ep_cat" not in found


def test_different_histories_yield_different_recall():
    """同一句话，不同经历的网络想起不同的东西。这个差异就是性格。"""
    saliences = {"ep_review": 0.6, "ep_hurt": 0.9, "ep_praise": 0.8, "ep_grow": 0.7}

    def build(pairs):
        net = Network()
        for nid, sal in saliences.items():
            net.add(nid, salience=sal)
        for _ in range(15):
            for a, b in pairs:
                net.co_activate({a: 1.0, b: 0.9})
            net.tick()
        return net

    hurt = build([("ep_review", "ep_hurt")])
    praised = build([("ep_review", "ep_praise"), ("ep_praise", "ep_grow")])

    a = {n for n, _ in hurt.spread({"ep_review": 1.0}, limit=5)}
    b = {n for n, _ in praised.spread({"ep_review": 1.0}, limit=5)}

    assert "ep_hurt" in a and "ep_hurt" not in b
    assert "ep_praise" in b and "ep_praise" not in a


def test_recall_reinforces_path():
    """回忆这个动作本身会改变网络 —— 想得越多，路越深。"""
    net = chain_network()
    before = net.weight("ep_report", "ep_boss")
    for _ in range(10):
        net.recall({"ep_nervous": 1.0}, limit=6)
    assert net.weight("ep_report", "ep_boss") > before


def test_edge_growth_is_s_shaped():
    """连线粗细也遵循 S 形：越粗越难再粗。"""
    net = Network()
    net.add("a")
    net.add("b")
    deltas = []
    prev = 0.0
    for _ in range(40):
        net.co_activate({"a": 1.0, "b": 1.0})
        w = net.weight("a", "b")
        deltas.append(w - prev)
        prev = w
    assert deltas[20] < max(deltas), "接近上限时增速必须放缓"
    assert prev < 1.0, "永远留一点余地"


def test_anchors_always_present():
    """常驻记忆永远在线，不参与检索竞争。

    人不需要"检索"才想起父母的名字。忘掉这类东西是最伤人的失败，
    所以直接绕开检索。
    """
    net = chain_network()
    net.add("ep_user", salience=0.9, anchor=True)
    for _ in range(3000):  # 长期不用
        net.tick()
    recalled = [nid for nid, _ in net.recall({"ep_nervous": 1.0}, limit=6, learn=False)]
    assert "ep_user" in recalled
    assert net.edge_count() == 0, "连线该淡光了"


def test_unused_edges_fade_and_prune():
    """用则强，不用则弛。连线会淡掉并从索引里摘除。"""
    net = chain_network()
    assert net.edge_count() > 0
    for _ in range(2000):
        net.tick()
    assert net.edge_count() == 0


def test_nodes_are_never_deleted():
    """遗忘是分区，不是删除。可以想不起来，不能失去来历。"""
    net = chain_network()
    count = len(net)
    for _ in range(5000):
        net.tick()
    assert len(net) == count, "节点一条都不该少"
    assert net.get("ep_panic") is not None, "查得到，只是想不起来"


def test_tiers_shift_over_time():
    """记忆会从热区滑向温区、冷区。"""
    net = chain_network()
    hot = [n for n in ["ep_report", "ep_boss"] if net.tier(n) == "热区"]
    assert hot, "刚被反复激活的该在热区"
    for _ in range(3000):
        net.tick()
    assert net.tier("ep_report") in ("温区", "冷区")


def test_salience_biases_activation():
    """重要的事更容易被想起来。"""
    net = Network()
    net.add("seed")
    net.add("trivial", salience=0.0)
    net.add("major", salience=1.0)
    net.link("seed", "trivial", 0.5)
    net.link("seed", "major", 0.5)
    scores = dict(net.spread({"seed": 1.0}, limit=5))
    assert scores["major"] > scores["trivial"]


def test_coactivation_width_is_bounded():
    """一次大范围回忆不该把网络连成一团糊。"""
    net = Network()
    ids = [f"n{i}" for i in range(40)]
    for nid in ids:
        net.add(nid)
    net.co_activate({nid: 1.0 for nid in ids})
    # 只有能量最高的 COACT_WIDTH 个互相连线
    from loam.core.network import COACT_WIDTH

    assert net.edge_count() <= COACT_WIDTH * (COACT_WIDTH - 1) // 2


def test_roundtrip_persistence():
    """网络能存能读，形状不变。"""
    net = chain_network()
    net.add("ep_user", anchor=True)
    data = net.to_dict()
    restored = Network.from_dict(data)

    assert len(restored) == len(net)
    assert restored.edge_count() == net.edge_count()
    assert restored.cycle == net.cycle
    assert restored.anchors() == net.anchors()
    assert abs(restored.weight("ep_report", "ep_boss") - net.weight("ep_report", "ep_boss")) < 1e-4


def test_seed_from_matches_normalises():
    """匹配分数转成起点能量时会归一化 —— 匹配只负责找门口。"""
    seeds = seed_from_matches([("a", 8.0), ("b", 4.0), ("c", 0.0)], cap=3)
    assert seeds["a"] == 1.0
    assert abs(seeds["b"] - 0.5) < 1e-9
    assert "c" not in seeds


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
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)