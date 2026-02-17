import os
import json
import re
from typing import Dict, Any
from nodes.script.config import ScriptConfig


def _build_materials_text(materials: list) -> str:
    return "\n\n".join([
        f"- {m.get('title', '')}: {m.get('content', '')[:500]}"
        for m in materials[:5]
    ])


def _build_story_prompt(topic: Dict[str, Any], config: ScriptConfig, materials_text: str) -> str:
    return f"""Generate a {config.target_duration_minutes}-minute podcast dialogue script.

Topic: {topic.get('title', '')}
Description: {topic.get('description', '')}

Materials:
{materials_text}

Requirements:
1. {config.num_hosts} hosts dialogue
2. Style: {config.dialogue_style}
3. Structure: opening + multiple mainline segments + discussion + closing
4. Mark each speaker

Return JSON:
{{
    "title": "Episode title",
    "description": "Episode description",
    "content_type": "story",
    "sections": [
        {{"id": "opening", "type": "opening", "label": "开场", "speaker": "Host A", "text": "..."}},
        {{"id": "mainline_1", "type": "mainline", "label": "主线一", "speaker": "Host A", "text": "..."}},
        {{"id": "discussion", "type": "discussion", "label": "延伸讨论", "speaker": "Host B", "text": "..."}},
        {{"id": "closing", "type": "closing", "label": "结尾", "speaker": "Host A", "text": "..."}}
    ],
    "dialogue": [
        {{"speaker": "Host A", "text": "dialogue content"}},
        {{"speaker": "Host B", "text": "dialogue content"}}
    ]
}}
"""


def _build_news_brief_prompt(topic: Dict[str, Any], config: ScriptConfig, materials_text: str) -> str:
    return f"""Generate a {config.target_duration_minutes}-minute news brief podcast dialogue script.

Topic: {topic.get('title', '')}
Description: {topic.get('description', '')}

Materials:
{materials_text}

Requirements:
1. {config.num_hosts} hosts dialogue
2. Style: {config.dialogue_style}
3. Structure: opening + {config.news_item_count} news items + closing
4. Each news item should include: event summary + key fact + impact
5. Mark each speaker

Return JSON:
{{
    "title": "Episode title",
    "description": "Episode description",
    "content_type": "news_brief",
    "sections": [
        {{"id": "opening", "type": "opening", "label": "开场导语", "speaker": "Host A", "text": "..."}},
        {{"id": "news_1", "type": "news_item", "label": "新闻一", "speaker": "Host A", "text": "..."}},
        {{"id": "news_2", "type": "news_item", "label": "新闻二", "speaker": "Host B", "text": "..."}},
        {{"id": "closing", "type": "closing", "label": "结尾总结", "speaker": "Host A", "text": "..."}}
    ],
    "dialogue": [
        {{"speaker": "Host A", "text": "dialogue content"}},
        {{"speaker": "Host B", "text": "dialogue content"}}
    ]
}}
"""


PROMPT_BUILDERS = {
    "story": _build_story_prompt,
    "news_brief": _build_news_brief_prompt,
}


def _normalize_script(content_type: str, raw_script: Dict[str, Any], topic: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_script, dict):
        raw_script = {}

    normalized_content_type = raw_script.get("content_type")
    if normalized_content_type not in PROMPT_BUILDERS:
        normalized_content_type = content_type

    normalized = {
        "title": raw_script.get("title") or topic.get("title", "Untitled"),
        "description": raw_script.get("description", ""),
        "content_type": normalized_content_type,
        "sections": raw_script.get("sections") if isinstance(raw_script.get("sections"), list) else [],
        "dialogue": raw_script.get("dialogue") if isinstance(raw_script.get("dialogue"), list) else [],
    }

    if not normalized["dialogue"] and normalized["sections"]:
        normalized["dialogue"] = [
            {
                "speaker": sec.get("speaker", "Host A"),
                "text": sec.get("text", ""),
            }
            for sec in normalized["sections"]
            if isinstance(sec, dict) and sec.get("text")
        ]

    return normalized


def run(state: Dict[str, Any], config: ScriptConfig = None) -> Dict[str, Any]:
    config = config or ScriptConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[ScriptNode] Starting script generation")
    topic = state.get("selected_topic", {})
    materials = state.get("selected_materials", [])

    try:
        if not topic or not materials:
            errors.append({"node": "script", "message": "Missing topic or materials"})
            state["logs"] = logs
            state["errors"] = errors
            return state

        script = _generate_script(topic, materials, config)
        state["script"] = script
        logs.append(f"[ScriptNode] Script done: {script.get('title', '')}")

        # Stage segmentation (merged from stages node)
        dialogue = script.get("dialogue", [])
        stages = []
        wpm = config.words_per_minute
        for i, line in enumerate(dialogue):
            text = line.get("text", "")
            word_count = len(text)
            duration = word_count / wpm * 60
            stages.append({
                "order": i,
                "speaker": line.get("speaker", ""),
                "text": text,
                "estimated_duration": round(duration, 1),
            })
        state["stages"] = stages
        total_dur = sum(s["estimated_duration"] for s in stages)
        logs.append(f"[ScriptNode] {len(stages)} segments, ~{total_dur:.0f}s total")
    except Exception as e:
        errors.append({"node": "script", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state


def _generate_script(topic: Dict, materials: list, config: ScriptConfig) -> Dict[str, Any]:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = config.api_base or os.environ.get("OPENAI_API_BASE", None)

    # 检查API密钥
    if not api_key:
        raise ValueError(
            "API key is required for script generation. "
            "Please set api_key in script node config or OPENAI_API_KEY environment variable."
        )

    kwargs = {
        "model": config.llm_model, 
        "api_key": api_key, 
        "temperature": config.temperature,
        "timeout": config.timeout,
        "max_retries": config.max_retries
    }
    if api_base:
        kwargs["base_url"] = api_base
    
    llm = ChatOpenAI(**kwargs)

    materials_text = _build_materials_text(materials)
    content_type = config.content_type if config.content_type in PROMPT_BUILDERS else "story"
    prompt = PROMPT_BUILDERS[content_type](topic, config, materials_text)

    system_content_map = {
        "story": "You are a professional podcast script writer.",
        "news_brief": "You are a professional news podcast editor skilled in concise daily briefings.",
    }
    messages = [
        SystemMessage(content=system_content_map.get(content_type, system_content_map["story"])),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    content = response.content
    json_match = re.search(r'\{.*\}', content, re.DOTALL)

    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return _normalize_script(content_type, parsed, topic)
        except json.JSONDecodeError:
            pass

    return _normalize_script(content_type, {
        "title": topic.get("title", "Untitled"),
        "description": "",
        "dialogue": [],
    }, topic)
