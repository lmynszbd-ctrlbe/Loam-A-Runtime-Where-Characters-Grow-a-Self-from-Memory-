"""赫布记忆网络。

只有一条规则，从神经科学抄来的：

    一起被激活的，连接就变强。

其余全是这条规则的后果：

* 记忆之间长出连线，所以联想能跳多步 —— 因为有路可走了。
* 每个角色的网络形状都不同，因为连线是各自的经历刻出来的。
* 因果关系不需要谁去教。反复共同出现的东西自己就连上了。
* 人格不存放在任何一处。它是"哪些记忆会被一起带出来"这件事本身。

检索不是每次重新算一遍相似度，而是让激活从起点顺着连线扩散出去。
粗的线传得远，细的线传不动。同一句话，不同的网络会带出完全不同的东西 ——
那个差异就是性格。

连线的生长沿用 growth.py 里同一个 S 形规律：越粗越难再粗，
长期不用会自己淡掉，淡到极细就从索引里摘掉（但节点永不删除）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------- 常量

#: 赫布强化的可塑率。
COACT_RATE = 0.30

#: 连线粗细上限。永远留一点余地。
EDGE_CEILING = 0.95

#: 回忆型共现的起始痕迹：两件事"后来被一起想起来"。
#: 这是间接证据 —— 也许只是当时的检索凑巧把它们放在了一起。
EDGE_SEED = 0.05

#: 亲历型共现的起始痕迹：两件事"发生在同一段经历里"。
#:
#: 比回忆型硬一个数量级，这是有意的。一起经历过和后来被一起想起
#: 不是同一种证据：前者是事实（这两件事真的在同一段时间里发生），
#: 后者是推测（检索觉得它们像）。把两者混为一谈的后果是同一段
#: 对话里的事连不起来，多跳联想全断在第一跳 —— 而"顺着经历走
#: 到字面毫不相干的旧事"正是整个项目要的东西。
EDGE_SEED_LIVED = 0.22

#: 初痕的力度折扣下限。
#: 一条连线一旦被刻下，就不允许细到剪枝线以下 —— 那等于没连。
#: 弱激活该表现为"痕浅"，不该表现为"根本没发生"。
SEED_FORCE_FLOOR = 0.4

#: 枢纽惩罚的度数阈值。连接超过此数量的节点视为"超级枢纽"。
#: 来源: heuristically_tuned —— 大部分节点度数在 1-5，超过 20 的极少。
HUB_DEGREE_THRESHOLD = 20

#: 枢纽惩罚的衰减指数。>1 表示超线性惩罚，度数越高衰减越剧烈。
#: 来源: heuristically_tuned —— 2.0 意味着度数翻倍则能量衰减到 1/4。
HUB_DECAY_EXPONENT = 2.0

#: 连线每个周期的自然衰减。用则强，不用则弛。
EDGE_DECAY = 0.995

#: 细到这个程度的连线从索引里摘掉（节点本身不动）。
PRUNE_BELOW = 0.015

#: 每跳的能量传递系数。决定联想能跳多远。
#: 偏高是有意的 —— 人的联想链条本来就能走好几步（明天 → 汇报 →
#: 上次被打断 → 那个打断我的人）。传递太低就退化成"只跳一步"，
#: 那正是现有检索方案的毛病。
TRANSMIT = 0.75

#: 能量低于此值就不再往外扩散，也不计入结果。
MIN_ENERGY = 0.008

#: 单次扩散的最大跳数。
MAX_HOPS = 4

#: 一次共同激活里最多互相连线的节点数。
#: 超过就只取能量最高的若干个 —— 否则一次大范围回忆会把网络连成一团糊。
COACT_WIDTH = 12

#: 显著性对激活的加成权重。重要的事更容易被想起来。
SALIENCE_GAIN = 0.35


# ---------------------------------------------------------------- 节点


@dataclass
class Node:
    """记忆网络里的一个节点，对应一条情景记忆。

    Attributes:
        id: 指向原始事件。
        salience: 这件事有多重要，[0, 1]。决定它多容易被激活。
        anchor: 常驻。不走检索，永远在线。
            用于"你是谁""你在意的人""正在进行的大事"这类东西 ——
            人不需要检索才想起父母的名字，忘掉这类东西是最伤人的失败。
        created_cycle: 出生周期。
        last_active_cycle: 上次被激活的周期。
        activations: 累计被激活次数。
    """

    id: str
    salience: float = 0.5
    anchor: bool = False
    created_cycle: int = 0
    last_active_cycle: int = 0
    activations: int = 0

    def __post_init__(self) -> None:
        self.salience = max(0.0, min(1.0, self.salience))


# ---------------------------------------------------------------- 网络


class Network:
    """一张会自己长连线的记忆网络。

    节点只增不减 —— 可以让它想不起来，但不能让它失去来历。
    连线会生长、会衰减、会被摘出索引，这才是"遗忘"发生的地方。
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, Node] = {}
        #: 邻接表。对称存两份，换取扩散时的读取速度。
        self._edges: Dict[str, Dict[str, float]] = {}
        self._cycle = 0

    # ------------------------------------------------------------ 基本操作

    @property
    def cycle(self) -> int:
        return self._cycle

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes

    def add(
        self,
        node_id: str,
        salience: float = 0.5,
        anchor: bool = False,
    ) -> Node:
        """加入一条记忆。已存在则只更新显著性上限。"""
        existing = self._nodes.get(node_id)
        if existing is not None:
            existing.salience = max(existing.salience, salience)
            existing.anchor = existing.anchor or anchor
            return existing
        node = Node(
            id=node_id,
            salience=salience,
            anchor=anchor,
            created_cycle=self._cycle,
            last_active_cycle=self._cycle,
        )
        self._nodes[node_id] = node
        self._edges.setdefault(node_id, {})
        return node

    def get(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def anchors(self) -> List[str]:
        """常驻记忆。永远在线，不参与竞争。"""
        return [n.id for n in self._nodes.values() if n.anchor]

    def weight(self, a: str, b: str) -> float:
        """两条记忆之间的连线粗细。0 表示没连上。"""
        return self._edges.get(a, {}).get(b, 0.0)

    def neighbors(self, node_id: str) -> Dict[str, float]:
        return dict(self._edges.get(node_id, {}))

    def edge_count(self) -> int:
        return sum(len(v) for v in self._edges.values()) // 2

    # ------------------------------------------------------------ 赫布规则

    def co_activate(
        self,
        activated: Dict[str, float],
        cycle: Optional[int] = None,
        lived: bool = False,
    ) -> int:
        """一起被想起来的记忆之间，连线变粗。

        这是整个模块唯一的学习规则。

        Args:
            activated: 节点 id -> 这次的激活能量。
            cycle: 周期号，默认用网络当前周期。
            lived: 这批节点是"同一段经历里亲历的"（True），还是
                "后来被一起回忆起的"（False）。亲历刻下的初痕更深，
                见 EDGE_SEED_LIVED。

        Returns:
            被强化的连线数量。
        """
        if cycle is None:
            cycle = self._cycle

        present = {k: v for k, v in activated.items() if k in self._nodes}
        if len(present) < 2:
            self._mark_active(present, cycle)
            return 0

        # 只让能量最高的若干个互相连线，否则一次大范围回忆会把网络连成一团糊
        top = sorted(present.items(), key=lambda kv: kv[1], reverse=True)[:COACT_WIDTH]

        strengthened = 0
        for i, (a, ea) in enumerate(top):
            for b, eb in top[i + 1 :]:
                # 推力取两者中较弱的那个 —— 一条记忆只是勉强被激活，
                # 不足以在它和别的东西之间刻下深痕。
                force = min(ea, eb)
                if force <= 0:
                    continue
                self._strengthen(a, b, force, lived=lived)
                strengthened += 1

        self._mark_active(present, cycle)
        return strengthened

    def _strengthen(self, a: str, b: str, force: float, lived: bool = False) -> None:
        """按 S 形规律加粗一条连线。"""
        w = self._edges[a].get(b, 0.0)
        if w <= 0.0:
            # 初次一起被想起 —— 刻下一道痕。深度取决于证据的种类
            # （亲历还是回忆）和当时的激活强度。
            # 力度只做折扣，且有下限：刻了就得算刻了，否则新生的连线
            # 还没长起来就被当成噪声清掉，网络永远长不出结构。
            seed = EDGE_SEED_LIVED if lived else EDGE_SEED
            w = seed * max(force, SEED_FORCE_FLOOR)
        base = max(w, EDGE_SEED)
        room = max(EDGE_CEILING - w, 0.0)
        new = min(w + COACT_RATE * base * room * force, EDGE_CEILING)
        self._edges[a][b] = new
        self._edges[b][a] = new

    def _mark_active(self, activated: Iterable[str], cycle: int) -> None:
        for node_id in activated:
            node = self._nodes.get(node_id)
            if node is not None:
                node.last_active_cycle = cycle
                node.activations += 1

    def link(self, a: str, b: str, weight: float) -> None:
        """手工连线。用于导入已知关系，或测试。"""
        if a not in self._nodes or b not in self._nodes:
            raise KeyError("连线的两端都必须先存在")
        w = max(0.0, min(EDGE_CEILING, weight))
        self._edges[a][b] = w
        self._edges[b][a] = w

    # ------------------------------------------------------------ 扩散激活

    def spread(
        self,
        seeds: Dict[str, float],
        limit: int = 20,
        max_hops: int = MAX_HOPS,
    ) -> List[Tuple[str, float]]:
        """让激活从起点顺着连线扩散出去。

        这是检索。不算相似度 —— 相似度只用来选起点（由调用方决定），
        起点之后走的是网络自己长出来的路。

        所以它能找到那些跟当前这句话一点都不像、但因果上相关的记忆：
        你说"我明天有点紧张"，字面上跟"上次汇报被打断"毫无重合，
        但如果这两件事在过去反复一起被想起，路就已经在那儿了。

        Args:
            seeds: 起点 id -> 初始能量。
            limit: 最多返回多少条。
            max_hops: 最多跳几步。

        Returns:
            (节点 id, 激活强度)，按强度降序。
        """
        energy: Dict[str, float] = {}
        frontier: Dict[str, float] = {}

        for node_id, e in seeds.items():
            if node_id in self._nodes and e > 0:
                energy[node_id] = energy.get(node_id, 0.0) + e
                frontier[node_id] = frontier.get(node_id, 0.0) + e

        for _ in range(max_hops):
            if not frontier:
                break
            nxt: Dict[str, float] = {}
            for src, e_src in frontier.items():
                if e_src < MIN_ENERGY:
                    continue
                for dst, w in self._edges.get(src, {}).items():
                    if w < PRUNE_BELOW:
                        continue
                    # 枢纽惩罚：度数越高的节点，能量传过去衰减越大
                    degree = len(self._edges.get(dst, {}))
                    hub_penalty = 1.0 / max(1.0, (degree / HUB_DEGREE_THRESHOLD) ** HUB_DECAY_EXPONENT)
                    passed = e_src * w * TRANSMIT * hub_penalty
                    if passed < MIN_ENERGY:
                        continue
                    energy[dst] = energy.get(dst, 0.0) + passed
                    nxt[dst] = nxt.get(dst, 0.0) + passed
            frontier = nxt

        # 显著性加成：重要的事更容易被想起来
        scored: List[Tuple[str, float]] = []
        for node_id, e in energy.items():
            node = self._nodes[node_id]
            scored.append((node_id, e * (1.0 + SALIENCE_GAIN * node.salience)))

        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:limit]

    def recall(
        self,
        seeds: Dict[str, float],
        limit: int = 20,
        max_hops: int = MAX_HOPS,
        learn: bool = True,
    ) -> List[Tuple[str, float]]:
        """一次完整的回忆：常驻在前，扩散结果在后，然后按赫布规则学习。

        `learn=True` 时，这次一起被想起来的东西之间连线会变粗。
        也就是说 —— 回忆这个动作本身会改变网络。想得越多，路越深。
        """
        anchored = [(a, float("inf")) for a in self.anchors()]
        anchor_ids = {a for a, _ in anchored}

        room = max(limit - len(anchored), 0)
        spread = [(i, s) for i, s in self.spread(seeds, limit=limit * 2, max_hops=max_hops) if i not in anchor_ids][:room]

        result = anchored + spread

        if learn and spread:
            # 常驻节点不参与共同激活 —— 它们永远在线，
            # 如果参与，就会跟所有东西连成一团。
            self.co_activate({i: s for i, s in spread})

        return result

    # ------------------------------------------------------------ 周期维护

    def tick(self) -> int:
        """推进一个周期：连线自然衰减，过细的摘出索引。

        Returns:
            本次被摘掉的连线数。
        """
        self._cycle += 1
        pruned = 0
        for a, nbrs in self._edges.items():
            for b in list(nbrs):
                w = nbrs[b] * EDGE_DECAY
                if w < PRUNE_BELOW:
                    del nbrs[b]
                    pruned += 1
                else:
                    nbrs[b] = w
        # 对称存储，每条边被数了两次
        return pruned // 2

    # ------------------------------------------------------------ 分区

    def tier(self, node_id: str, hot_window: int = 200) -> str:
        """一条记忆现在处于哪个区。

        热区 —— 参与每次回忆。
        温区 —— 不参与常规检索，只有被明确追问或顺着连线扩散才够到。
        冷区 —— 日常完全想不起来了。但它还在，来历还查得到。

        这就是"遗忘"：功能上确实想不起来了，但线没断，翻旧账还翻得动。
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(node_id)
        if node.anchor:
            return "常驻"

        age = self._cycle - node.last_active_cycle
        degree = sum(1 for w in self._edges.get(node_id, {}).values() if w >= 0.10)

        if age <= hot_window and (degree >= 2 or node.salience >= 0.7):
            return "热区"
        if age <= hot_window * 10 or degree >= 1:
            return "温区"
        return "冷区"

    def stats(self) -> Dict[str, object]:
        """网络概况，给人看的。"""
        tiers: Dict[str, int] = {}
        for node_id in self._nodes:
            t = self.tier(node_id)
            tiers[t] = tiers.get(t, 0) + 1
        weights = [w for nbrs in self._edges.values() for w in nbrs.values()]
        return {
            "节点": len(self._nodes),
            "连线": self.edge_count(),
            "周期": self._cycle,
            "分区": tiers,
            "平均连线粗细": round(sum(weights) / len(weights), 4) if weights else 0.0,
            "最粗连线": round(max(weights), 4) if weights else 0.0,
        }

    # ------------------------------------------------------------ 持久化

    def to_dict(self) -> Dict[str, object]:
        """导出为可 JSON 序列化的结构。"""
        return {
            "cycle": self._cycle,
            "nodes": [
                {
                    "id": n.id,
                    "salience": n.salience,
                    "anchor": n.anchor,
                    "created_cycle": n.created_cycle,
                    "last_active_cycle": n.last_active_cycle,
                    "activations": n.activations,
                }
                for n in self._nodes.values()
            ],
            # 只存一半，避免体积翻倍
            "edges": [
                [a, b, round(w, 5)]
                for a, nbrs in self._edges.items()
                for b, w in nbrs.items()
                if a < b
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Network":
        net = cls()
        net._cycle = int(data.get("cycle", 0))  # type: ignore[arg-type]
        for raw in data.get("nodes", []):  # type: ignore[union-attr]
            node = Node(**raw)  # type: ignore[arg-type]
            net._nodes[node.id] = node
            net._edges.setdefault(node.id, {})
        for a, b, w in data.get("edges", []):  # type: ignore[union-attr]
            if a in net._nodes and b in net._nodes:
                net._edges[a][b] = w
                net._edges[b][a] = w
        return net


# ---------------------------------------------------------------- 辅助


def seed_from_matches(matches: Sequence[Tuple[str, float]], cap: int = 5) -> Dict[str, float]:
    """把"字面/语义匹配"的结果转成扩散起点。

    匹配只负责找门口在哪，进门之后走的是网络自己的路。
    """
    top = sorted(matches, key=lambda kv: kv[1], reverse=True)[:cap]
    if not top:
        return {}
    peak = top[0][1] or 1.0
    return {node_id: score / peak for node_id, score in top if score > 0}