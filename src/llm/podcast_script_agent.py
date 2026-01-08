from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph


class PodcastState(TypedDict, total=False):
    news: str
    style_profile: str
    outline: str
    draft: Dict[str, str]
    critique: Dict[str, Any]
    revisions: int
    final_outputs: Dict[str, str]


@dataclass
class ScriptResult:
    outputs: Dict[str, str]
    score: int
    revisions: int
    issues: List[str]
    outline: str
    critique: Dict[str, Any]


def _extract_json_obj(text: str) -> Dict[str, Any]:
    s = (text or "").strip()
    if not s:
        return {}

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    if s.startswith("```"):
        i = s.find("\n")
        s2 = s[i + 1 :] if i != -1 else ""
        j = s2.rfind("```")
        if j != -1:
            s2 = s2[:j]
        s2 = s2.strip()
        if s2:
            try:
                obj = json.loads(s2)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                pass

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s3 = s[start : end + 1]
        try:
            obj = json.loads(s3)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    return {}


def _draft_to_text(draft: Dict[str, str]) -> str:
    parts: List[str] = []
    for k in ("opening", "history", "briefs", "deep_dive", "outro"):
        v = (draft or {}).get(k, "")
        if v:
            parts.append(v.strip())
    return "\n\n".join(parts)


def _normalize_outputs(d: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in ("opening", "history", "briefs", "deep_dive", "outro"):
        v = d.get(k, "") if isinstance(d, dict) else ""
        out[k] = str(v or "").strip()
    out["full_script"] = _draft_to_text(out)
    return out


OUTLINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是资深中文播客编导。你的目标是为播客脚本先做提纲拆解。"),
        (
            "user",
            "风格要求：{style_profile}\n\n素材：\n{news}\n\n"
            "请输出一个用于播客写作的提纲：\n"
            "- 5段以内\n"
            "- 每段 1-2 句\n"
            "- 指出每段的过渡点\n"
            "只输出提纲正文，不要写成可播稿。",
        ),
    ]
)

DRAFT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是中文播客主播。请按提纲写出可直接给TTS的口播文稿，并分段输出。",
        ),
        (
            "user",
            "风格要求：{style_profile}\n\n提纲：\n{outline}\n\n"
            "素材：\n{news}\n\n"
            "请输出严格JSON，不要多余文字。字段：\n"
            "opening, history, briefs, deep_dive, outro\n\n"
            "硬性要求：\n"
            "- 单句尽量不超过 30 字\n"
            "- 避免新闻稿腔\n"
            "- 避免固定口头禅：下面我们来看/据悉/此外/简单说/翻译一下/你可以这么理解\n"
            "- 段落之间过渡自然\n",
        ),
    ]
)

CRITIC_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是播客总监，负责质量把关。必须输出JSON，不要多余文字。"),
        (
            "user",
            "风格要求：{style_profile}\n\n稿件：\n{draft_text}\n\n"
            "输出JSON字段：score(0-100), is_tts_friendly(bool), is_human_like(bool), issues(list), rewrite_guidance(str)",
        ),
    ]
)

REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是中文播客主播，按修改意见重写。输出必须是严格JSON。"),
        (
            "user",
            "风格要求：{style_profile}\n\n原稿：\n{draft_text}\n\n"
            "评审问题：{issues}\n\n修改建议：{rewrite_guidance}\n\n"
            "请输出严格JSON，不要多余文字。字段：opening, history, briefs, deep_dive, outro\n\n"
            "重写要求：\n"
            "- 单句尽量不超过 30 字\n"
            "- 更像聊天，允许少量口语重复\n"
            "- 过渡自然\n",
        ),
    ]
)


def _invoke_chat(llm, prompt: ChatPromptTemplate, variables: Dict[str, Any], temperature: float) -> str:
    messages = prompt.format_messages(**variables)
    def _role(t: str) -> str:
        if t == "human":
            return "user"
        if t == "ai":
            return "assistant"
        if t == "system":
            return "system"
        return "user"

    payload = [{"role": _role(m.type), "content": m.content} for m in messages]
    resp = llm.chat(payload, temperature=temperature)
    return str((resp or {}).get("content", ""))


def make_outline(state: PodcastState, llm, temperature: float) -> PodcastState:
    outline = _invoke_chat(
        llm,
        OUTLINE_PROMPT,
        {"news": state["news"], "style_profile": state["style_profile"]},
        temperature,
    ).strip()
    return {"outline": outline}


def make_draft(state: PodcastState, llm, temperature: float) -> PodcastState:
    raw = _invoke_chat(
        llm,
        DRAFT_PROMPT,
        {
            "news": state["news"],
            "style_profile": state["style_profile"],
            "outline": state["outline"],
        },
        temperature,
    )
    draft = _extract_json_obj(raw)
    return {"draft": _normalize_outputs(draft)}


def critique_draft(state: PodcastState, llm, temperature: float) -> PodcastState:
    draft_text = _draft_to_text(state.get("draft", {}))
    raw = _invoke_chat(
        llm,
        CRITIC_PROMPT,
        {"draft_text": draft_text, "style_profile": state["style_profile"]},
        temperature,
    )
    critique = _extract_json_obj(raw)
    return {"critique": critique}


def rewrite(state: PodcastState, llm, temperature: float) -> PodcastState:
    critique = state.get("critique", {}) or {}
    draft_text = _draft_to_text(state.get("draft", {}))
    raw = _invoke_chat(
        llm,
        REWRITE_PROMPT,
        {
            "draft_text": draft_text,
            "issues": critique.get("issues", []),
            "rewrite_guidance": critique.get("rewrite_guidance", ""),
            "style_profile": state["style_profile"],
        },
        temperature,
    )
    new_draft = _extract_json_obj(raw)
    return {
        "draft": _normalize_outputs(new_draft),
        "revisions": int(state.get("revisions", 0)) + 1,
    }


def finalize(state: PodcastState) -> PodcastState:
    return {"final_outputs": state.get("draft", {})}


def _should_rewrite(state: PodcastState, threshold: int, max_revisions: int) -> str:
    critique = state.get("critique", {}) or {}
    revisions = int(state.get("revisions", 0) or 0)

    try:
        score = int(critique.get("score", 0) or 0)
    except Exception:
        score = 0

    if score >= threshold:
        return "finalize"
    if revisions >= max_revisions:
        return "finalize"
    return "rewrite"


def build_podcast_agent(*, llm, temperature: float, threshold: int, max_revisions: int):
    g = StateGraph(PodcastState)

    g.add_node("outline", lambda s: make_outline(s, llm, temperature))
    g.add_node("draft", lambda s: make_draft(s, llm, temperature))
    g.add_node("critic", lambda s: critique_draft(s, llm, temperature=0.2))
    g.add_node("rewrite", lambda s: rewrite(s, llm, temperature))
    g.add_node("finalize", finalize)

    g.set_entry_point("outline")
    g.add_edge("outline", "draft")
    g.add_edge("draft", "critic")

    g.add_conditional_edges(
        "critic",
        lambda s: _should_rewrite(s, threshold=threshold, max_revisions=max_revisions),
        {"rewrite": "rewrite", "finalize": "finalize"},
    )
    g.add_edge("rewrite", "critic")
    g.add_edge("finalize", END)

    return g.compile()


def generate_segmented_script(
    *,
    llm,
    news: str,
    style_profile: str,
    temperature: float = 0.7,
    threshold: int = 78,
    max_revisions: int = 2,
) -> ScriptResult:
    app = build_podcast_agent(
        llm=llm,
        temperature=temperature,
        threshold=threshold,
        max_revisions=max_revisions,
    )

    init: PodcastState = {
        "news": news,
        "style_profile": style_profile,
        "revisions": 0,
    }
    out: PodcastState = app.invoke(init)

    critique = out.get("critique", {}) or {}
    try:
        score = int(critique.get("score", 0) or 0)
    except Exception:
        score = 0

    final_outputs = out.get("final_outputs", {}) or {}
    return ScriptResult(
        outputs=final_outputs,
        score=score,
        revisions=int(out.get("revisions", 0) or 0),
        issues=list(critique.get("issues", []) or []) if isinstance(critique, dict) else [],
        outline=str(out.get("outline", "") or ""),
        critique=critique if isinstance(critique, dict) else {},
    )
