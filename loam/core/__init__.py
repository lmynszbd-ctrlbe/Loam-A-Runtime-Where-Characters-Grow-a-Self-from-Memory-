"""loam 的内生机制层。

这一层不调用任何模型，不碰网络，不读写文件。它只包含规律本身：
特质怎么生长（growth），记忆怎么连接和被想起（network）。

规则要少、要局部、要一致，然后放手。规则写在过程层，不写在结果层 ——
不去限制"自述最多改多少字"，而是规定"每条特质怎么增长"。
"""

from loam.core.growth import Evidence, Trait
from loam.core.network import Network, Node, seed_from_matches

__all__ = ["Evidence", "Trait", "Network", "Node", "seed_from_matches"]