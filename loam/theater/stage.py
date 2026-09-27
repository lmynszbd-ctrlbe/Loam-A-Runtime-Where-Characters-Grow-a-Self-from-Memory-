"""loam.theater.stage: 虚拟剧场舞台总线 (Virtual Theater Stage Bus).

设计哲学：
- 剧场是自我生长的最高试炼场。
- 单个 AI 面对人类提问往往容易沦为被动的“问答助手”；但在虚拟剧场舞台中，
  多个具有独立记忆、情绪共振态、内心执念（蔡加尼克张力）与他者镜像的角色共处一个舞台空间。
- 舞台总线负责多角色会话分发、轮转发言推进、心智对抗/共鸣激发，以及协同消化（Mutual Digestion）。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple


class TheaterStage:
    """虚拟剧场舞台总线。"""

    def __init__(self, stage_id: str = "main_stage") -> None:
        self.stage_id = stage_id
        self.actors: Dict[str, Any] = {}          # actor_name -> LoamService or adapter
        self.transcript: List[Dict[str, Any]] = [] # 全局舞台场记记录
        self._last_speaker: Optional[str] = None

    def register_actor(self, name: str, service: Any) -> None:
        """角色登台注册。"""
        self.actors[name] = service

    def unregister_actor(self, name: str) -> None:
        """角色下台注销。"""
        self.actors.pop(name, None)

    def list_actors(self) -> List[str]:
        """查看当前舞台上的所有角色。"""
        return list(self.actors.keys())

    def post_line(
        self,
        speaker: str,
        content: str,
        session: Optional[str] = None,
        wrote_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        """向舞台总线发送一句台词。
        舞台总线会将这句台词同步投递到舞台上所有角色的 Journal 中，保证每个角色的记忆世界都能如实记录。
        """
        sess = session or f"stage_{self.stage_id}"
        ts = wrote_at or time.time()
        record = {
            "speaker": speaker,
            "content": content,
            "session": sess,
            "timestamp": ts,
        }
        self.transcript.append(record)
        self._last_speaker = speaker

        for actor_name, svc in self.actors.items():
            journal = getattr(svc, "journal", None)
            if journal is not None:
                try:
                    last_t = journal.last_turn(actor_name, session=sess)
                    journal.append(
                        character=actor_name,
                        session=sess,
                        turn=last_t + 1,
                        role=speaker,
                        content=content,
                        wrote_at=ts,
                    )
                except Exception:
                    pass

        return record

    def select_next_speaker(self, preferred: Optional[str] = None) -> Optional[str]:
        """戏剧动力学发言角色决选器：
        1. 若指定 preferred 且在场，直接使用。
        2. 戏剧张力优先原则：优先让带有最高活跃执念张力（Tension）的角色开口表达/倾诉。
        3. 否则在非上一轮发言者中轮换。
        """
        if not self.actors:
            return None
        if preferred and preferred in self.actors:
            return preferred

        candidates = [name for name in self.actors if name != self._last_speaker]
        if not candidates:
            candidates = list(self.actors.keys())

        # 检查候选角色的最高心结张力
        highest_tension = -1.0
        chosen = candidates[0]
        for name in candidates:
            svc = self.actors[name]
            memory = getattr(svc, "memory", None)
            if memory and hasattr(memory, "get_active_drives"):
                try:
                    drives = memory.get_active_drives(limit=1)
                    if drives:
                        t = float(drives[0].tension)
                        if t > highest_tension:
                            highest_tension = t
                            chosen = name
                except Exception:
                    pass

        return chosen

    def step_dialogue(
        self,
        speaker: Optional[str] = None,
        session: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """推进一轮即兴戏剧对白：
        选定角色 -> 基于自身性格/心境/心结/他者镜像装配上下文 -> 生成台词 -> 广播回舞台。
        """
        current_speaker = self.select_next_speaker(preferred=speaker)
        if not current_speaker:
            return {"error": "舞台上没有可用角色"}

        svc = self.actors[current_speaker]
        sess = session or f"stage_{self.stage_id}"

        # 寻找舞台上的对话对手 (partner)
        partners = [name for name in self.actors if name != current_speaker]
        partner_id = partners[0] if partners else "user"

        # 取最近几条台词作为上下文 query
        recent_text = ""
        if self.transcript:
            recent_text = self.transcript[-1]["content"]
        query_text = topic or recent_text

        # 装配该角色视角的 L4 上下文 (包含 Subjective Lens, Drives, Mirror of other)
        ctx_pack = None
        if hasattr(svc, "build_context"):
            try:
                ctx_pack = svc.build_context(query=query_text, partner_id=partner_id)
            except Exception:
                pass

        rendered_context = ctx_pack.render() if ctx_pack and hasattr(ctx_pack, "render") else ""

        # 生成台词
        line_content = ""
        brain = getattr(svc, "brain", None)
        if brain and getattr(brain, "available", False):
            sys_prompt = (
                f"你是戏剧舞台上的角色【{current_speaker}】。\n"
                f"你正在与【{partner_id}】同台对戏。\n"
                "请完全基于你内在的性格特质、当下心境、未化解的心结与对眼前之人的心智揣摩进行即兴回应。\n"
                "要求：\n"
                "1. 绝不出戏，不说 AI 助手腔，像真实而鲜活的人一样回应。\n"
                "2. 语言简练克制、富于潜台词与戏剧张力（20~60字）。\n"
                "3. 直接输出角色台词，不要带名字前缀或舞台括号说明。"
            )
            dialogue_history = "\n".join(
                [f"{rec['speaker']}: {rec['content']}" for rec in self.transcript[-6:]]
            )
            user_prompt = (
                f"【你的内在自性画像与心境记忆】：\n{rendered_context}\n\n"
                f"【舞台近况】：\n{dialogue_history or '（大幕初启，二人初次对视）'}\n\n"
                f"请说出【{current_speaker}】的下一句台词："
            )
            try:
                text, _ = brain.ask(sys_prompt, user_prompt, max_tokens=256, temperature=0.7)
                line_content = text.strip().strip('"').strip('“').strip('”')
            except Exception:
                line_content = ""

        if not line_content:
            # 离线启发式台词生成器（忠实体现五重自性体系状态）
            mood_str = getattr(ctx_pack, "mood", None) if ctx_pack else ""
            drives = getattr(ctx_pack, "drives", []) if ctx_pack else []
            mirror = getattr(ctx_pack, "mirror", {}) if ctx_pack else {}

            if drives and drives[0].get("theme"):
                theme = drives[0]["theme"]
                line_content = f"对于【{theme}】，我心中始终有一份悬念难以释怀……你当真觉得事情如表面那般简单？"
            elif mirror and mirror.get("summary"):
                summary = mirror["summary"]
                line_content = f"看着你的神情，总觉得你{summary}……我们之间，或许可以把话挑得更明白些。"
            elif recent_text:
                line_content = f"你方才说的那些话，我都在听。但在我看来，事情或许有另一重未曾道出的意味。"
            else:
                line_content = f"舞台已经备好，夜色渐深。我们到底在回避些什么？"

        # 广播回舞台
        posted = self.post_line(speaker=current_speaker, content=line_content, session=sess)

        return {
            "speaker": current_speaker,
            "line": line_content,
            "partner": partner_id,
            "session": sess,
            "timestamp": posted["timestamp"],
            "context": ctx_pack.as_dict() if ctx_pack and hasattr(ctx_pack, "as_dict") else None,
        }

    def run_scene(
        self,
        rounds: int = 3,
        session: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """连续运行多轮即兴戏剧对白。"""
        if initial_prompt:
            self.post_line("旁白", initial_prompt, session=session)

        scene_results = []
        for _ in range(max(1, rounds)):
            res = self.step_dialogue(session=session)
            if "error" in res:
                break
            scene_results.append(res)
        return scene_results

    def trigger_mutual_digestion(self) -> Dict[str, Any]:
        """协同心智消化：
        让舞台上所有演员同步对刚才的对白进行消化，
        双方的感知透镜、心结张力、他者镜像以及潜意识梦境在此共同生长蜕变。
        """
        reports: Dict[str, Any] = {}
        for name, svc in self.actors.items():
            if hasattr(svc, "digest_once"):
                try:
                    rep = svc.digest_once()
                    reports[name] = rep.as_dict() if hasattr(rep, "as_dict") else rep
                except Exception as exc:
                    reports[name] = {"error": str(exc)}
            elif hasattr(svc, "digester") and hasattr(svc.digester, "digest_once"):
                try:
                    rep = svc.digester.digest_once()
                    reports[name] = rep.as_dict() if hasattr(rep, "as_dict") else rep
                except Exception as exc:
                    reports[name] = {"error": str(exc)}
        return reports
