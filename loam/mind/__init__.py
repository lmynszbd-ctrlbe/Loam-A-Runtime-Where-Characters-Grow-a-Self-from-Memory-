"""向内的那一层 —— 唯一会调用模型、也唯一会改动人格的地方。

这里跟 core 的分工很硬：
core 是规律（不碰网络、不碰文件、不调模型），mind 是判断（调模型）。
所以规律永远可测、可复现；判断出错了也只会让这一批料重煮一次，
不会污染已经长成的形状。
"""

from .context import ContextBuilder, ContextPack
from .digest import Digester, DigestReport, Grower
from .llm import (
    Brain,
    BrainError,
    BrainUnavailable,
    ScriptedBrain,
    load_brain,
    parse_json,
    write_secrets_template,
)

__all__ = [
    "ContextBuilder",
    "ContextPack",
    "Digester",
    "DigestReport",
    "Grower",
    "Brain",
    "BrainError",
    "BrainUnavailable",
    "ScriptedBrain",
    "load_brain",
    "parse_json",
    "write_secrets_template",
]