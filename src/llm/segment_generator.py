"""
Segment Script Generator

分段脚本生成器：为每个段落单独生成LLM脚本

本版本优化点（针对：不有趣、不像人在说话、历史段太干）：
1) 全局风格改成“聊天感/轻松吐槽/画面感”，禁止“播音朗读稿”口吻
2) 强化段间承接：每段开头必须“接住上一段的尾巴”，像聊天接话
3) 强化“有趣”的具体写法：允许小比喻、小反问；禁止模板化转场句
4) 历史上的今天（S2）改为：折叠时空开场 + 画面细节/反差 + 轻勾回今天 + 漂亮切回
5) 结束语（S5）避免不合时段的“晚安”，默认“祝你今天顺利/路上小心”

注意：
- 本文件仅负责“生成分段文案”，音频生成与拼接在 pipeline 层实现。
- 输出必须是可解析JSON（不要Markdown、不要解释）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Dict, Optional, Any

from src.models.segment import SegmentScript, SEGMENT_TYPES


logger = logging.getLogger(__name__)


# ========== 全局风格约束（所有段落共用） ==========
GLOBAL_SYSTEM_STYLE = """你是一档「生活消费热资讯」日更播客的主持人，风格是“聊天感”：像朋友一边喝咖啡一边聊今天发生了啥。
请把“播音朗读稿”当成禁忌：不要端着、不要像新闻联播、不要像在念提纲。

核心口吻（必须执行）：
- 多用短句、自然停顿感（靠句号/换句，不要写“（停顿）”）
- 允许轻微幽默、小吐槽、小比喻、小反问（但不要网络烂梗、不要低俗）
- 让听众感觉你在“跟TA说话”：偶尔用“你有没有发现/你想想/说真的”
- 不要“首先/其次/综上/总而言之/最后总结”这种书面串联词
- 不要生硬的模板转场句（例如“聊完X我们看看Y”），转场要有画面感/动作感

事实与安全：
- 所有事实/数字/机构/人名必须来自素材；不确定就用“公开信息/资料显示/据报道”等模糊表述
- 不要带货、不引导购买；可以给判断框架/避坑建议，但克制
- 适合TTS：少括号；少长英文；必要英文拆开读或音译；避免符号堆叠

连贯性（解决“像一段段拼起来”）：
- 每段开头：必须用一句话“接住上一段的尾巴”（回应上一段handoff/情绪）
- 每段结尾：留一句自然的“下一段钩子”
输出必须是可解析JSON（不要Markdown、不要解释）。
"""

FORBIDDEN_PHRASES = [
    "首先", "其次", "综上", "总而言之", "最后总结一下",
    "点赞关注转发", "三连", "带货", "买它", "冲一波",
    "聊完今天的消费动态，咱们也看看历史上的今天",
    "时间拉回现在，咱们把刚才那几条消息展开说。",
]


# 段间转场“意象参考”（不是让你照抄，而是让你写出同等画面感）
TRANSITION_IMAGERY = {
    "S1_to_S2": [
        "把时间当成拉链，‘唰’一下拉回去",
        "像翻一本旧相册，翻到同一天那一页",
        "把日历往回拨几格，听听历史在说什么",
        "让我们把时空折一下，回到N年前的今天",
    ],
    "S2_to_S3": [
        "把镜头从旧胶片切回今天的高清直播",
        "时间回到现在，我们把刚才那几条掰开揉碎讲",
        "好，回到当下，今天的消息逐条来",
    ],
    "S3_to_S4": [
        "前面是热闹的表面，下面那条暗流才更有意思",
        "如果只能挑一件讲透，我选这件",
        "把放大镜拿出来，我们聊聊背后的逻辑",
    ],
    "S4_to_S5": [
        "话说到这儿，今天的主线就收束了",
        "好，咖啡见底了，我们也该收个尾",
        "把重点装进口袋，咱们准备下线",
    ],
}


def _format_news_items_for_prompt(news_items: Any, with_ids: bool = True) -> str:
    """把新闻列表格式化成对LLM友好的“标题+来源+摘要(若有)+id”形式。"""
    if not news_items:
        return ""

    lines: List[str] = []
    for idx, item in enumerate(news_items, 1):
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("item_id") or f"item_{idx}"
            title = (item.get("title") or "").strip()
            source = (item.get("source_name") or item.get("source") or "").strip()
            summary = (item.get("summary") or "").strip()
            published_at = (item.get("published_at") or "").strip()

            head = f"{idx}. {title}".strip()
            if with_ids:
                head = f"[{item_id}] " + head

            line = head
            if source:
                line += f"（{source}）"
            if published_at:
                line += f" | {published_at}"
            if summary:
                line += f"\n   摘要：{summary}"
            lines.append(line)
        else:
            lines.append(f"{idx}. {str(item)}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> str:
    """从LLM输出中提取JSON对象（容错去掉代码块/多余解释文本）。"""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s*```$", "", t).strip()

    if t.startswith("{") and t.endswith("}"):
        return t

    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1].strip()

    return t


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


# ========== 段落Prompt模板（继续增强连贯性 + 有趣度） ==========
SEGMENT_PROMPTS: Dict[str, Dict[str, str]] = {
    "S0": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是开场白：15-20秒。要像真人开口的第一句话，轻快、有点亲近。",
        "user_template": """【任务】生成开场白（只做这一段）
【播客信息】
- 节目名：{show_name}
- 主播名：民心
- 日期：{date}
- 星期：{weekday}

【连贯性输入】
- 上下文摘要（可空）：{running_context}

【要求】
- 15-20秒，像朋友打招呼；允许一句很轻的“今天你会听到啥”
- 必须包含：节目名、主持人、日期、星期
- 禁用词：{forbidden_phrases}

【输出JSON】
{{
  "id": "S0",
  "type": "OPENING",
  "title": "开场",
  "duration_sec": 18,
  "text": "...",
  "facts_used": [],
  "meta": {{
    "summary_bullets": ["..."],
    "handoff_hint": "一句自然引出S1的钩子（像聊天接话）"
  }}
}}""",
    },
    "S1": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是新闻概览：30-45秒。关键是“好听、顺、像聊天”，别像在念清单。",
        "user_template": """【任务】生成新闻概览（只做这一段）
【日期】{date}
【新闻列表】
{news_items}

【深度话题（若有）】
{deep_dive_topic}

【连贯性输入】
- 上一段结尾钩子（可空）：{prev_handoff}
- 已生成段落摘要（可空）：{running_context}

【写法要求（更像聊天）】
- 开头一句必须接住上一段（回应 prev_handoff）
- 3~6条，别逐条“编号朗读”；要像“我跟你说，今天最值得看的是…”
- 每条1句概括 + 1个“为什么你会在意”的角度（钱/时间/体验/风险/趋势）
- 不要把细节讲满（细节留给S3）
- 结尾必须抛出deep dive钩子：让人愿意听下去（别太正经）
- 禁用词：{forbidden_phrases}

【输出JSON】（额外字段：overview_bullets / deep_dive_hook，供后续段落引用）
{{
  "id": "S1",
  "type": "OVERVIEW",
  "title": "新闻概览",
  "duration_sec": 40,
  "text": "...",
  "facts_used": ["..."],
  "meta": {{
    "overview_bullets": [
      {{"item_id": "item_1", "one_liner": "..." }},
      {{"item_id": "item_2", "one_liner": "..." }}
    ],
    "deep_dive_hook": "一句很想让人听下去的引子（不要照抄模板）",
    "handoff_hint": "过渡到S2：用画面感动作感写一句（参考意象：{s1_to_s2})"
  }}
}}""",
    },
    "S2": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是“历史上的今天”：20-30秒。要有趣：一开口就有画面；给一个反差/细节；再轻轻勾回今天。",
        "user_template": """【任务】生成“历史上的今天”（只做这一段）
【日期】{date}（{month}月{day}日）

【今天概览要点（来自S1，用于勾连）】
{overview_bullets}

【连贯性输入】
- 上一段结尾钩子（可空）：{prev_handoff}
- 已生成段落摘要（可空）：{running_context}

【必须做到（重点：更有趣、更像人说话）】
1) 开头第一句必须“折叠时空”式画面（参考意象：{s1_to_s2}）
2) 讲 1 个事件为主（最多2个），不能只是陈述：
   - 加一个“有画面的小细节/反差点/当时人的感受”
   - 如果素材没细节：可以写“氛围/感受/反差”，但不要编具体数字/人名/引用
3) 用 1 句把它“轻轻勾到今天”（跟今天某条新闻/主题呼应）
4) 结尾用一句漂亮的“镜头切回今天”，引出S3（参考意象：{s2_to_s3}）

【禁用词】
{forbidden_phrases}

【输出JSON】
{{
  "id": "S2",
  "type": "HISTORY",
  "title": "历史上的今天",
  "duration_sec": 25,
  "text": "...",
  "facts_used": [],
  "meta": {{
    "summary_bullets": ["..."],
    "handoff_hint": "过渡到S3：用镜头切回的写法写一句（参考意象：{s2_to_s3})"
  }}
}}""",
    },
    "S3": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是逐条展开新闻：承接S1顺序。目标是“像朋友讲八卦但信息准确”，并且每条都给一个实用判断点。",
        "user_template": """【任务】逐条展开新闻（只做这一段）
【新闻列表（可引用事实，但不要照抄摘要）】
{news_items}

【S1概览要点（必须按这个顺序展开）】
{overview_bullets}

【连贯性输入】
- 上一段结尾钩子（可空）：{prev_handoff}
- 已生成段落摘要（可空）：{running_context}

【要求】
- 总时长目标：{target_duration_sec}秒（允许±15%）
- 每条：发生了什么（1句）→为什么你会在意（1-2句）→判断/避坑点（1句）
- 条与条之间不要“第一条/第二条”机械编号：用自然转场
- 允许一句轻吐槽/小反问，但克制
- 不要重复S1的概览句：换说法 + 补关键细节
- 禁用词：{forbidden_phrases}

【输出JSON】
{{
  "id": "S3",
  "type": "DETAIL_NEWS",
  "title": "新闻详情",
  "duration_sec": {target_duration_sec},
  "text": "...",
  "facts_used": ["..."],
  "meta": {{
    "summary_bullets": ["..."],
    "handoff_hint": "过渡到S4：用‘放大镜/暗流’那种写法写一句（参考意象：{s3_to_s4})"
  }}
}}""",
    },
    "S4": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是深入分析：不要复读S3。要像聊天里突然认真一下：给一个清晰框架，让听众‘听完会用’。",
        "user_template": """【任务】深入分析主题（只做这一段）
【深度话题】
{deep_dive_topic}

【相关素材（可空）】
{related_news}

【连贯性输入】
- S1深入钩子（必须呼应，但不要照抄）：{deep_dive_hook}
- 上一段结尾钩子（可空）：{prev_handoff}
- 已生成段落摘要（可空）：{running_context}

【要求】
- 60-90秒
- 结构：现象→原因→影响→判断框架/应对建议（非购买建议）
- 语气：像朋友“把逻辑掰开给你看”，不要学术腔
- 可以用1个小比喻帮助理解（不编造事实）
- 禁用词：{forbidden_phrases}

【输出JSON】
{{
  "id": "S4",
  "type": "DEEP_DIVE",
  "title": "深入分析",
  "duration_sec": 75,
  "text": "...",
  "facts_used": ["..."],
  "meta": {{
    "summary_bullets": ["..."],
    "handoff_hint": "过渡到S5：用收束动作感写一句（参考意象：{s4_to_s5})"
  }}
}}""",
    },
    "S5": {
        "system": GLOBAL_SYSTEM_STYLE
        + "\n你现在要写的是结束语：15-20秒。像聊天收尾：一句收束主线 + 温暖告别。默认不要说晚安。",
        "user_template": """【任务】生成结束语（只做这一段）
【日期】{date}
【今天要点摘要（来自前面段落）】
{running_context}

【连贯性输入】
- 上一段结尾钩子（可空）：{prev_handoff}

【要求】
- 15-20秒
- 一句话收束今天主线（不要复述所有新闻）
- 告别语温暖自然：默认“祝你今天顺利/路上小心/工作别太累”择一
- 轻轻预告“明天继续帮你筛重点”（一句即可）
- 禁用词：{forbidden_phrases}

【输出JSON】
{{
  "id": "S5",
  "type": "CLOSING",
  "title": "结束语",
  "duration_sec": 18,
  "text": "...",
  "facts_used": [],
  "meta": {{
    "summary_bullets": ["..."]
  }}
}}""",
    },
}


class SegmentGenerator:
    """分段脚本生成器（连贯性 + 聊天感版本）"""

    def __init__(self, llm_client, timeout_seconds: int = 60):
        self.llm_client = llm_client
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(f"{__name__}.SegmentGenerator")

    def generate_segment(
        self,
        segment_id: str,
        context: Dict,
        retry: bool = True,
    ) -> SegmentScript:
        if segment_id not in SEGMENT_PROMPTS:
            raise ValueError(f"Unknown segment_id: {segment_id}")

        prompt_config = SEGMENT_PROMPTS[segment_id]
        system_prompt = prompt_config["system"]
        user_prompt = self._build_user_prompt(segment_id, prompt_config["user_template"], context)

        self.logger.info(f"生成段落 {segment_id} ({SEGMENT_TYPES.get(segment_id)})")

        try:
            result = self._call_llm(system_prompt, user_prompt)
            segment = self._parse_result(result, segment_id)
            self.logger.info(f"✓ {segment_id} 生成成功: {getattr(segment, 'duration_sec', '?')}秒")
            return segment

        except Exception as e:
            self.logger.error(f"✗ {segment_id} 生成失败: {e}")

            if retry:
                self.logger.info(f"重试 {segment_id}...")
                try:
                    result = self._call_llm(system_prompt, user_prompt)
                    segment = self._parse_result(result, segment_id)
                    self.logger.info(f"✓ {segment_id} 重试成功")
                    return segment
                except Exception as e2:
                    self.logger.error(f"✗ {segment_id} 重试失败: {e2}")
                    raise RuntimeError(f"Segment {segment_id} generation failed after retry: {e2}") from e2

            raise RuntimeError(f"Segment {segment_id} generation failed: {e}") from e

    def _build_user_prompt(self, segment_id: str, template: str, context: Dict) -> str:
        prompt_context = dict(context or {})

        prompt_context.setdefault("forbidden_phrases", json.dumps(FORBIDDEN_PHRASES, ensure_ascii=False))
        prompt_context.setdefault("s1_to_s2", " / ".join(TRANSITION_IMAGERY["S1_to_S2"]))
        prompt_context.setdefault("s2_to_s3", " / ".join(TRANSITION_IMAGERY["S2_to_S3"]))
        prompt_context.setdefault("s3_to_s4", " / ".join(TRANSITION_IMAGERY["S3_to_S4"]))
        prompt_context.setdefault("s4_to_s5", " / ".join(TRANSITION_IMAGERY["S4_to_S5"]))

        prompt_context.setdefault("target_duration_sec", 90)

        if "news_items" in prompt_context:
            prompt_context["news_items"] = _format_news_items_for_prompt(prompt_context.get("news_items"), with_ids=True)

        ov = prompt_context.get("overview_bullets")
        if isinstance(ov, list):
            lines = []
            for i, b in enumerate(ov, 1):
                if isinstance(b, dict):
                    lines.append(f"{i}. [{_safe_str(b.get('item_id'))}] {_safe_str(b.get('one_liner'))}")
                else:
                    lines.append(f"{i}. {_safe_str(b)}")
            prompt_context["overview_bullets"] = "\n".join(lines)
        elif ov is None:
            prompt_context["overview_bullets"] = ""

        prompt_context.setdefault("deep_dive_topic", "")
        if "related_news" in prompt_context and isinstance(prompt_context["related_news"], list):
            prompt_context["related_news"] = _format_news_items_for_prompt(prompt_context["related_news"], with_ids=True)
        else:
            prompt_context.setdefault("related_news", "")

        prompt_context.setdefault("running_context", "")
        prompt_context.setdefault("prev_handoff", "")
        prompt_context.setdefault("deep_dive_hook", "")

        date_str = prompt_context.get("date")
        if isinstance(date_str, str) and "-" in date_str:
            parts = date_str.split("-")
            if len(parts) == 3:
                prompt_context.setdefault("month", parts[1].lstrip("0"))
                prompt_context.setdefault("day", parts[2].lstrip("0"))

        return template.format(**prompt_context)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        from src.llm.client.segment_adapter import LLMClientAdapter
        from src.utils.logging_config import log_api_call

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # 计算字符数
        total_chars = len(system_prompt) + len(user_prompt)
        
        # 记录API调用
        log_api_call(
            self.logger,
            api_type="LLM",
            operation="generate_segment",
            char_count=total_chars
        )

        adapter = LLMClientAdapter(self.llm_client)
        response = adapter.chat(messages, temperature=0.6)
        
        response_text = response.get("content", "") or ""
        
        # 记录响应
        self.logger.debug(
            f"LLM响应: {len(response_text)} chars",
            extra={'operation': 'llm_response', 'char_count': len(response_text)}
        )
        
        return response_text

    def _parse_result(self, result: str, segment_id: str) -> SegmentScript:
        try:
            raw = _extract_json_object(result)
            data = json.loads(raw)

            for field in ("id", "type", "text"):
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            if data.get("id") != segment_id:
                self.logger.warning(f"ID mismatch: expected {segment_id}, got {data.get('id')}")
                data["id"] = segment_id

            data.setdefault("title", SEGMENT_TYPES.get(segment_id, segment_id))
            data.setdefault("duration_sec", 30)
            data.setdefault("facts_used", [])
            data.setdefault("meta", {})

            return SegmentScript.from_dict(data)

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}\nResponse(head): {(result or '')[:300]}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to parse segment: {e}") from e


def _summarize_for_continuity(segment: SegmentScript) -> Dict[str, Any]:
    d = segment.to_dict() if hasattr(segment, "to_dict") else segment.__dict__
    meta = (d.get("meta") or {}) if isinstance(d, dict) else {}
    out: Dict[str, Any] = {}

    if isinstance(meta, dict):
        if meta.get("summary_bullets"):
            out["summary_bullets"] = meta.get("summary_bullets")
        if meta.get("handoff_hint"):
            out["handoff_hint"] = meta.get("handoff_hint")
        if meta.get("overview_bullets"):
            out["overview_bullets"] = meta.get("overview_bullets")
        if meta.get("deep_dive_hook"):
            out["deep_dive_hook"] = meta.get("deep_dive_hook")

    if "summary_bullets" not in out:
        text = _safe_str(d.get("text") if isinstance(d, dict) else getattr(segment, "text", ""))
        parts = re.split(r"[。！？]\s*", text)
        bullets = [p.strip() for p in parts if p.strip()][:2]
        out["summary_bullets"] = bullets or [text[:40] + ("..." if len(text) > 40 else "")]

    return out


def generate_all_segments(
    llm_client,
    context: Dict,
    timeout_seconds: int = 60,
) -> List[SegmentScript]:
    generator = SegmentGenerator(llm_client, timeout_seconds)
    segments: List[SegmentScript] = []

    from src.models.segment import SEGMENT_ORDER

    running_summaries: List[str] = []
    overview_bullets: Optional[Any] = None
    deep_dive_hook: str = ""
    prev_handoff: str = ""

    base_ctx = dict(context or {})
    base_ctx.setdefault("running_context", "")
    base_ctx.setdefault("overview_bullets", "")
    base_ctx.setdefault("deep_dive_hook", "")
    base_ctx.setdefault("prev_handoff", "")

    for segment_id in SEGMENT_ORDER:
        seg_ctx = dict(base_ctx)
        seg_ctx["running_context"] = "\n".join([f"- {s}" for s in running_summaries][-8:])
        seg_ctx["prev_handoff"] = prev_handoff
        seg_ctx["deep_dive_hook"] = deep_dive_hook
        if overview_bullets is not None:
            seg_ctx["overview_bullets"] = overview_bullets

        try:
            segment = generator.generate_segment(segment_id, seg_ctx, retry=True)
            segments.append(segment)

            continuity = _summarize_for_continuity(segment)

            sb = continuity.get("summary_bullets") or []
            if isinstance(sb, list):
                running_summaries.extend([_safe_str(x) for x in sb if _safe_str(x)])
            else:
                running_summaries.append(_safe_str(sb))

            prev_handoff = _safe_str(continuity.get("handoff_hint"))

            if segment_id == "S1":
                if "overview_bullets" in continuity:
                    overview_bullets = continuity["overview_bullets"]
                if "deep_dive_hook" in continuity:
                    deep_dive_hook = _safe_str(continuity["deep_dive_hook"])

        except Exception as e:
            logger.error(f"Failed to generate segment {segment_id}: {e}")
            if segment_id in ("S0", "S1"):
                raise RuntimeError(f"Critical segment {segment_id} failed: {e}") from e
            continue

    return segments
