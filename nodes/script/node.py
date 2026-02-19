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
    if config.num_hosts == 1:
        host_desc = "solo narration (1 host, all lines by Host A)"
        structure_desc = "opening + story content + reflection + closing (all by Host A)"
        sections_example = (
            '{"id": "opening", "type": "opening", "label": "开场", "speaker": "Host A", "text": "..."},\n'
            '        {"id": "mainline_1", "type": "mainline", "label": "主线一", "speaker": "Host A", "text": "..."},\n'
            '        {"id": "reflection", "type": "reflection", "label": "思考感悟", "speaker": "Host A", "text": "..."},\n'
            '        {"id": "closing", "type": "closing", "label": "结尾", "speaker": "Host A", "text": "..."}'
        )
        dialogue_example = (
            '{"speaker": "Host A", "text": "..."},\n'
            '        {"speaker": "Host A", "text": "..."}'
        )
    else:
        host_desc = f"multi-host dialogue ({config.num_hosts} hosts: Host A, Host B)"
        structure_desc = "opening + multiple mainline segments + cross-host discussion + closing"
        sections_example = (
            '{"id": "opening", "type": "opening", "label": "开场", "speaker": "Host A", "text": "..."},\n'
            '        {"id": "mainline_1", "type": "mainline", "label": "主线一", "speaker": "Host A", "text": "..."},\n'
            '        {"id": "discussion", "type": "discussion", "label": "延伸讨论", "speaker": "Host B", "text": "..."},\n'
            '        {"id": "closing", "type": "closing", "label": "结尾", "speaker": "Host A", "text": "..."}'
        )
        dialogue_example = (
            '{"speaker": "Host A", "text": "..."},\n'
            '        {"speaker": "Host B", "text": "..."}'
        )
    target_chars = config.target_duration_minutes * config.words_per_minute
    return f"""Generate a {config.target_duration_minutes}-minute Chinese podcast script.

Topic: {topic.get('title', '')}
Description: {topic.get('description', '')}

Materials:
{materials_text}

Requirements:
1. Format: {host_desc}
2. Style: {config.dialogue_style}
3. Structure: {structure_desc}
4. Mark each speaker
5. ALL content MUST be in Chinese (普通话)
6. Total script length: ~{target_chars}字 (each section should have substantial content, NOT placeholder text)

Return JSON (sections only, no dialogue field needed):
{{
    "title": "节目标题",
    "description": "节目简介",
    "content_type": "story",
    "sections": [
        {sections_example}
    ]
}}
"""


def _build_news_brief_prompt(topic: Dict[str, Any], config: ScriptConfig, materials_text: str) -> str:
    if config.num_hosts == 1:
        host_desc = "solo narration (1 host, all lines by Host A)"
        news_section_speaker = "Host A"
    else:
        host_desc = f"multi-host dialogue ({config.num_hosts} hosts: Host A, Host B)"
        news_section_speaker = "Host A\", \"Host B"
    target_chars = config.target_duration_minutes * config.words_per_minute
    return f"""Generate a {config.target_duration_minutes}-minute Chinese news brief podcast script.

Topic: {topic.get('title', '')}
Description: {topic.get('description', '')}

Materials:
{materials_text}

Requirements:
1. Format: {host_desc}
2. Style: {config.dialogue_style}
3. Structure: opening + {config.news_item_count} news items + closing
4. Each news item: event summary + key fact + impact
5. Mark each speaker
6. ALL content MUST be in Chinese (普通话)
7. Total script length: ~{target_chars}字 (each section should have substantial content, NOT placeholder text)

Return JSON (sections only, no dialogue field needed):
{{
    "title": "节目标题",
    "description": "节目简介",
    "content_type": "news_brief",
    "sections": [
        {{"id": "opening", "type": "opening", "label": "开场导语", "speaker": "Host A", "text": "将开场内容写在这里"}},
        {{"id": "news_1", "type": "news_item", "label": "新闻一", "speaker": "Host A", "text": "将第一条新闻内容写在这里"}},
        {{"id": "closing", "type": "closing", "label": "结尾总结", "speaker": "Host A", "text": "将结尾内容写在这里"}}
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

    normalized["dialogue"] = [
        {
            "speaker": sec.get("speaker", "Host A"),
            "text": sec.get("text", ""),
        }
        for sec in normalized["sections"]
        if isinstance(sec, dict) and sec.get("text")
    ] or normalized["dialogue"]

    return normalized


def run(state: Dict[str, Any], config: ScriptConfig = None) -> Dict[str, Any]:
    config = config or ScriptConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    topic = state.get("selected_topic", {})
    materials = state.get("selected_materials", [])
    runtime_config = state.get("runtime_config", {})
    debug_mode = runtime_config.get("debug_mode", {}).get("enabled", False)
    
    logs.append(f"[ScriptNode] ========== 节点启动 ==========")
    logs.append(f"[ScriptNode] 启动时间: {datetime.now().isoformat()}")
    logs.append(f"[ScriptNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[ScriptNode] 输入: selected_topic='{topic.get('title', 'N/A')[:50]}', selected_materials={len(materials)} items")
    logs.append(f"[ScriptNode] 配置: content_type={config.content_type}, target_duration={config.target_duration_minutes}min, num_hosts={config.num_hosts}")
    if debug_mode:
        logs.append(f"[ScriptNode] ⚡ DEBUG MODE ACTIVE")
        logs.append(f"[ScriptNode]   效果说明: 使用精简Prompt (不超150字), timeout=30s, 个人化输出将被截断")
    else:
        logs.append(f"[ScriptNode] 运行模式: 正常 (debug_mode=False)")

    try:
        if not topic or not materials:
            errors.append({"node": "script", "message": "Missing topic or materials"})
            state["logs"] = logs
            state["errors"] = errors
            return state

        logs.append(f"[ScriptNode] 生成脚本中... (debug_mode={debug_mode})")
        script = _generate_script(topic, materials, config, debug_mode=debug_mode)
        state["script"] = script
        logs.append(f"[ScriptNode] 脚本生成完成: {script.get('title', '')}")

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
        logs.append(f"[ScriptNode] 分段完成: {len(stages)} segments, 预计时长 ~{total_dur:.0f}s")
    except Exception as e:
        errors.append({"node": "script", "message": str(e), "detail": str(e)})
        logs.append(f"[ScriptNode] ✗ 错误: {str(e)}")
    
    _elapsed = _time.time() - _t0
    logs.append(f"[ScriptNode] ========== 节点完成 ==========")
    logs.append(f"[ScriptNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    script = state.get("script", {})
    stages = state.get("stages", [])
    logs.append(f"[ScriptNode] 输出: script.title='{script.get('title', 'N/A')[:50]}', stages={len(stages)} segments")
    if script:
        logs.append(f"[ScriptNode] 内容类型: {script.get('content_type', 'N/A')}, 对话行数: {len(script.get('dialogue', []))}")
    logs.append(f"[ScriptNode] 错误数: {len([e for e in errors if e.get('node') == 'script'])}")

    state["logs"] = logs
    state["errors"] = errors
    return state


def _generate_script(topic: Dict, materials: list, config: ScriptConfig) -> Dict[str, Any]:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = config.api_base or os.environ.get("OPENAI_API_BASE", None)

    # 检查API密鑰
    if not api_key:
        raise ValueError(
            "API key is required for script generation. "
            "Please set api_key in script node config or OPENAI_API_KEY environment variable."
        )

    effective_timeout = min(config.timeout, 30) if debug_mode else config.timeout
    kwargs = {
        "model": config.llm_model, 
        "api_key": api_key, 
        "temperature": config.temperature,
        "timeout": effective_timeout,
        "max_retries": config.max_retries
    }
    if api_base:
        kwargs["base_url"] = api_base
    
    llm = ChatOpenAI(**kwargs)

    materials_text = _build_materials_text(materials)
    content_type = config.content_type if config.content_type in PROMPT_BUILDERS else "story"
    if debug_mode:
        prompt = f"""[DEBUG MODE] 生成一个极简单的测试脚本。
主题: {topic.get('title', '')[:50]}
Return minimal JSON: {{"title":"测试标题","description":"测试","content_type":"{content_type}","sections":[],"dialogue":[{{"speaker":"Host","text":"DEBUG MODE测试内容"}}]}}"""
    else:
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
