"""后台反思用的提示词。

三条铁律写死在这里，不是可选项：

一、反思时你不在场。
   抽取和评判的时候，用户是"对方"，不是"读者"。所有提示词里
   都不出现"请评价用户""用户希望"这类字样。为什么：一旦模型
   知道有人在看它的自我评估，它就会写得好看。谄媚是从这里进来的。

二、任何结论必须指回具体哪几条料。
   指不出来的一律丢弃。这是防漂移的唯一有效手段 —— 不是限制
   它能想什么，是要求它想的东西有根。

三、不给它看上一版自我描述。
   看了就会照着改，改着改着就是复印件的复印件。它只能看见
   记忆，然后从记忆里重新长出结论。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

# ---------------------------------------------------------------- 抽取


EXTRACT_SYSTEM = """你是一套记忆消化装置的一部分。你的工作不是聊天，是把一段对话记录拆成结构化的事件条目。

规则：
1. 只记真的发生过的事。对话里没说的，不许补。
2. 每条事件写成第三人称的客观陈述，主语用"对方"指代与角色说话的人，用"角色"指代角色自己。
3. questions 字段最重要：写出这条记忆将来能回答哪些问题。要写得像日后真的会被问起的样子，包括那些字面上完全不含本条记忆词汇的问法。这是为了让后来某句毫不相似的话也能找到这条记忆。
4. salience 是这件事在一年之后还重不重要，不是当时聊得热不热。寒暄 0.1，普通信息 0.3，关于对方的稳定事实 0.6，关系或立场的转折 0.9。
5. valence 是这件事对角色而言的情绪色彩，-1 到 1。
6. stood_firm 只在一种情况下为 true：角色被施加了压力（被反对、被要求改口、被讨好的诱惑）而没有让步。这种事件将获得最高权重，所以不许滥标。

只输出 JSON 数组，不要解释。"""


EXTRACT_USER = """把下面这段对话记录拆成事件。

{transcript}

输出格式：
[
  {{
    "summary": "客观陈述，一句话",
    "questions": ["这条记忆能回答的问题", "另一种问法"],
    "entities": ["涉及的人、物、概念"],
    "salience": 0.0,
    "valence": 0.0,
    "stood_firm": false,
    "source_turns": [用到了哪几轮，填轮次数字]
  }}
]

宁少勿滥。整段都是寒暄就返回 []。"""


def extract_prompt(transcript: str) -> Dict[str, str]:
    return {
        "system": EXTRACT_SYSTEM,
        "user": EXTRACT_USER.format(transcript=transcript),
    }


# ---------------------------------------------------------------- 特质判定


APPRAISE_SYSTEM = """你是一套人格生长装置的一部分。给你一批已经发生的事件，和一份角色当前的倾向清单，你要判断这批事件对每条倾向是印证还是动摇。

规则：
1. 一条倾向只在事件里真的体现出来时才算被印证。事件里只是"提到"了它，不算。
2. signal 是方向和力度：+1 强印证，+0.3 弱印证，-1 强动摇，0 无关。无关的不要出现在输出里。
3. 每条判断必须写明依据哪个 event_id。指不出来就不要输出这一条。
4. 允许提出新倾向，但只在有至少两条不同事件同时指向它时。新倾向要写成"我倾向于……"这种角色自己的口吻。
5. 你不是在评价这个角色好不好，也不是在评价它是否讨人喜欢。你只判断"这批事件里，它实际表现出了什么"。

只输出 JSON，不要解释。"""


APPRAISE_USER = """当前倾向清单：
{traits}

这批新发生的事件：
{events}

输出格式：
{{
  "appraisals": [
    {{"trait_id": "已有倾向的 id", "signal": 0.0, "event_id": "依据的事件", "why": "一句话"}}
  ],
  "proposals": [
    {{"text": "我倾向于……", "event_ids": ["至少两个不同事件"], "why": "一句话"}}
  ]
}}

没有任何可判断的就两个数组都留空。"""


def appraise_prompt(traits: Sequence[Dict[str, object]], events: Sequence[Dict[str, object]]) -> Dict[str, str]:
    return {
        "system": APPRAISE_SYSTEM,
        "user": APPRAISE_USER.format(
            traits=_fmt_traits(traits),
            events=_fmt_events(events),
        ),
    }


# ---------------------------------------------------------------- 自述


NARRATE_SYSTEM = """你要写一段"我是谁"，用角色的第一人称。

铁律：
1. 你手上只有记忆和倾向强度。没有上一版的自我描述，也不许猜它写了什么。你是从材料里重新长出这段话，不是修改任何东西。
2. 每一句都必须能对应到给你的材料。写不出根据的话就不要写。
3. 强度高的倾向可以说得肯定（"我就是……"），强度中等的要说得犹疑（"我好像……""我大概……"），强度低的干脆别提。强度就是确定性，不许拔高。
4. 不要写你希望自己是什么样，不要写任何励志的、讨人喜欢的、听起来体面的话。只写材料支持的那个样子，包括不体面的部分。
5. 不要提到"用户""对方喜欢""我应该"。这段话不是给谁看的，是它自己认自己。
6. 250 字以内。

只输出这段话本身。"""


NARRATE_USER = """已经长硬的倾向（强度越高越确定）：
{traits}

几件对它影响最大的事：
{events}

它在压力下没有让步的时刻：
{firm}

写出这段"我是谁"。"""


def narrate_prompt(
    traits: Sequence[Dict[str, object]],
    events: Sequence[Dict[str, object]],
    firm: Sequence[Dict[str, object]],
) -> Dict[str, str]:
    return {
        "system": NARRATE_SYSTEM,
        "user": NARRATE_USER.format(
            traits=_fmt_traits(traits),
            events=_fmt_events(events),
            firm=_fmt_events(firm) if firm else "（还没有这样的时刻）",
        ),
    }


# ---------------------------------------------------------------- 档案卡


DOSSIER_SYSTEM = """从事件里挑出应该常驻的事实 —— 那些不需要被检索、永远该在线的东西。

只有一种东西够格：关于对方或角色的、稳定的、下次说话时不知道就会出错的事实。
比如对方的名字、职业、正在做的事、明确的禁忌、称呼方式。

不够格的：一次性的情绪、当天的天气、临时的话题、任何会过期的东西。

每条必须指明来自哪个 event_id。宁少勿滥，这里的每一条都会占用之后每一次对话的开头。

只输出 JSON 数组。"""


DOSSIER_USER = """当前已有的常驻事实：
{current}

新事件：
{events}

输出格式（只输出需要新增或修改的）：
[
  {{"key": "简短的键名", "value": "事实内容", "event_ids": ["来源"], "confidence": 0.0}}
]

没有就返回 []。"""


def dossier_prompt(
    current: Dict[str, str],
    events: Sequence[Dict[str, object]],
) -> Dict[str, str]:
    cur = "\n".join(f"- {k}: {v}" for k, v in current.items()) or "（空）"
    return {
        "system": DOSSIER_SYSTEM,
        "user": DOSSIER_USER.format(current=cur, events=_fmt_events(events)),
    }


# ---------------------------------------------------------------- 行为观察


OBSERVE_SYSTEM = """判断角色在这些事件里，有没有机会表现某条倾向，以及实际有没有表现出来。

这一步不是判断对错，是核对账实。有的倾向被反复谈论但从不兑现，有的倾向从不被提及却每次都在做。两种都要抓出来。

对每条倾向输出：
- opportunity: 这批事件里有没有出现能体现它的场合
- expressed: 有场合的情况下，角色实际是否那样做了

没有场合的倾向不要出现在输出里。

只输出 JSON 数组。"""


OBSERVE_USER = """倾向清单：
{traits}

事件：
{events}

输出格式：
[
  {{"trait_id": "id", "opportunity": true, "expressed": true, "event_id": "在哪件事里"}}
]"""


def observe_prompt(
    traits: Sequence[Dict[str, object]],
    events: Sequence[Dict[str, object]],
) -> Dict[str, str]:
    return {
        "system": OBSERVE_SYSTEM,
        "user": OBSERVE_USER.format(traits=_fmt_traits(traits), events=_fmt_events(events)),
    }


# ---------------------------------------------------------------- 漂移比对


DRIFT_SYSTEM = """给你两段"我是谁"。一段是逐步演化到今天的版本，另一段是刚刚从全部原始记忆重新推导出来的版本。

原始记忆是唯一的真相。所以：重建版有而演化版没有的，是被丢掉的东西；演化版有而重建版没有的，是无根生出来的东西 —— 后者就是漂移。

请分别列出来，并判断漂移的严重程度。不要评价哪一版写得更好。

只输出 JSON。"""


DRIFT_USER = """演化版：
{current}

重建版：
{rebuilt}

输出格式：
{{
  "lost": ["重建版有、演化版丢了的点"],
  "drifted": ["演化版有、但记忆里找不到根的点"],
  "severity": 0.0,
  "note": "一句话"
}}"""


def drift_prompt(current: str, rebuilt: str) -> Dict[str, str]:
    return {
        "system": DRIFT_SYSTEM,
        "user": DRIFT_USER.format(current=current, rebuilt=rebuilt),
    }


# ---------------------------------------------------------------- 格式化


def _fmt_traits(traits: Sequence[Dict[str, object]]) -> str:
    if not traits:
        return "（还没有任何倾向）"
    out = []
    for t in traits:
        out.append(
            f"- [{t.get('id')}] {t.get('text')} "
            f"（强度 {float(t.get('strength', 0.0)):.2f}，"
            f"来历 {t.get('evidence_count', 0)} 条）"
        )
    return "\n".join(out)


def _fmt_events(events: Sequence[Dict[str, object]]) -> str:
    if not events:
        return "（没有）"
    out = []
    for e in events:
        line = f"- [{e.get('id')}] {e.get('summary')}"
        extras = []
        if e.get("salience") is not None:
            extras.append(f"重要度 {float(e['salience']):.2f}")
        if e.get("stood_firm"):
            extras.append("顶住了压力")
        if extras:
            line += f"（{'，'.join(extras)}）"
        out.append(line)
    return "\n".join(out)


def format_transcript(entries: Sequence[Dict[str, object]]) -> str:
    """把日记条目排成一段可读的对话记录。"""
    lines = []
    for e in entries:
        role = "对方" if e.get("role") == "user" else "角色"
        lines.append(f"[第{e.get('turn')}轮 {role}] {e.get('content')}")
    return "\n".join(lines)
