import json
import os
import re
from typing import Any

from nodes.script.config import ScriptConfig
from protocol.llm_client import LLMClient
from protocol.morning_news import (
    build_fact_cards,
    build_run_report,
    generate_deterministic_script,
    script_to_stages,
    select_news_topics,
)
from protocol.node_runner import NodeContext
from protocol.presets import get_default_preset


def _build_facts_text(facts: list[dict[str, Any]]) -> str:
    lines = []
    for fact in facts[:5]:
        lines.append(
            "\n".join(
                [
                    f"- id: {fact.get('id', '')}",
                    f"  title: {fact.get('title', '')}",
                    f"  claim: {fact.get('claim', '')}",
                    f"  summary: {fact.get('summary', '')}",
                    f"  source: {fact.get('source_title', '')} {fact.get('source_url', '')}",
                    f"  published_at: {fact.get('published_at', '')}",
                ]
            )
        )
    return "\n".join(lines)


def _build_news_brief_prompt(topic: dict[str, Any], config: ScriptConfig, facts_text: str) -> str:
    target_chars = config.target_duration_minutes * config.words_per_minute
    return f"""Generate a Chinese solo morning news brief podcast script.

Preset: {config.preset_id}
Topic: {topic.get("title", "今日新闻早报")}
Description: {topic.get("description", "")}
Target duration: {config.target_duration_minutes} minutes (~{target_chars} Chinese chars)
Host count: 1
Tone: {config.tone}
Language: {config.language}

Fact cards:
{facts_text}

Rules:
1. Use only the facts above for factual claims.
2. Return structured segments, not a plain essay.
3. Each news_item segment MUST cite source_fact_ids.
4. Use segment types: opening, news_item, transition, context, closing.
5. Keep it commute-friendly and concise.

Return strict JSON:
{{
  "title": "节目标题",
  "description": "节目简介",
  "content_type": "news_brief",
  "preset_id": "morning_news_brief",
  "num_hosts": 1,
  "segments": [
    {{
      "id": "seg_001",
      "type": "opening",
      "title": "开场",
      "text": "...",
      "source_fact_ids": ["fact_001"],
      "estimated_seconds": 20
    }},
    {{
      "id": "seg_002",
      "type": "news_item",
      "title": "...",
      "text": "...",
      "source_fact_ids": ["fact_001"],
      "estimated_seconds": 45
    }}
  ]
}}
"""


def _normalize_script(
    raw_script: dict[str, Any],
    topic: dict[str, Any],
    facts: list[dict[str, Any]],
    config: ScriptConfig,
) -> dict[str, Any]:
    if not isinstance(raw_script, dict):
        raw_script = {}

    fact_ids = {fact.get("id") for fact in facts if isinstance(fact, dict)}
    normalized_segments: list[dict[str, Any]] = []
    raw_segments = raw_script.get("segments") or raw_script.get("sections") or []
    if isinstance(raw_segments, list):
        for idx, segment in enumerate(raw_segments):
            if not isinstance(segment, dict) or not segment.get("text"):
                continue
            source_fact_ids = [
                str(fact_id)
                for fact_id in segment.get("source_fact_ids", [])
                if fact_id in fact_ids or str(fact_id) in fact_ids
            ]
            text = str(segment.get("text", "")).strip()
            normalized_segments.append(
                {
                    "id": segment.get("id") or f"seg_{idx + 1:03d}",
                    "type": segment.get("type") or "news_item",
                    "title": segment.get("title") or segment.get("label") or "",
                    "text": text,
                    "source_fact_ids": source_fact_ids,
                    "estimated_seconds": int(segment.get("estimated_seconds") or max(6, len(text) / 6.5)),
                    "speaker": segment.get("speaker", "Host A"),
                }
            )

    if not normalized_segments:
        return generate_deterministic_script(
            facts,
            _preset_from_config(config),
            episode_id="",
            title=topic.get("title", "通勤早咖啡：今日新闻简报"),
        )

    script = {
        "title": raw_script.get("title") or topic.get("title") or "通勤早咖啡：今日新闻简报",
        "description": raw_script.get("description") or "单人新闻早报，面向通勤路上的快速收听。",
        "content_type": "news_brief",
        "preset_id": config.preset_id,
        "num_hosts": 1,
        "language": config.language,
        "segments": normalized_segments,
        "generated_by": raw_script.get("generated_by", "llm"),
    }
    script["sections"] = [
        {
            "id": segment["id"],
            "type": segment["type"],
            "label": segment["title"],
            "speaker": segment.get("speaker", "Host A"),
            "text": segment["text"],
            "source_fact_ids": segment["source_fact_ids"],
            "estimated_seconds": segment["estimated_seconds"],
        }
        for segment in normalized_segments
    ]
    script["dialogue"] = [
        {"speaker": segment.get("speaker", "Host A"), "text": segment["text"]}
        for segment in normalized_segments
    ]
    return script


def run(state: dict[str, Any], config: ScriptConfig = None) -> dict[str, Any]:
    config = config or ScriptConfig()
    ctx = NodeContext("ScriptNode", state)
    topic = state.get("selected_topic", {}) or {"title": "通勤早咖啡：今日新闻早报"}
    materials = state.get("selected_materials", [])
    facts = state.get("facts", [])

    ctx.log_start(
        f"输入: topic='{topic.get('title', 'N/A')[:50]}', materials={len(materials)}, "
        f"facts={len(facts)} | preset={config.preset_id}, content_type={config.content_type}, "
        f"target_duration={config.target_duration_minutes}min, num_hosts={config.num_hosts}",
        uses_llm=True,
    )

    try:
        if config.content_type != "news_brief" or config.num_hosts != 1:
            ctx.log(
                "当前产品默认路径要求单人 news_brief；本次执行将收敛为 morning_news_brief。"
            )
            config.content_type = "news_brief"
            config.num_hosts = 1

        if not facts:
            state.setdefault("migration_warnings", []).append(
                "script node generated facts as compatibility fallback; run facts node before script"
            )
            facts = build_fact_cards(materials, limit=max(config.news_item_count, 5))
            state["facts"] = facts
            ctx.log(f"事实卡片生成完成: {len(facts)} cards")

        if not facts:
            ctx.add_error("script", "Missing facts for script generation")
            ctx.log_end("输出: (无脚本 — 缺少事实卡片)")
            return ctx.finalize(state)

        preset = _preset_from_config(config)
        state["preset"] = preset
        if not state.get("selected_topics"):
            state["selected_topics"] = select_news_topics(facts, config.news_item_count)

        script = _generate_script(topic, facts, config, ctx)
        script["id"] = f"{state.get('episode_id', 'episode')}_script_generated"
        state["script"] = script
        state["stages"] = script_to_stages(script)

        if not state.get("edited_script"):
            state["edited_script"] = {
                **script,
                "id": f"{script.get('id', 'script')}_editable",
                "edited_from": script.get("id", "script.generated"),
                "edit_mode": "initial_editable_copy",
            }

        build_run_report(state)
        ctx.log(
            f"脚本生成完成: {script.get('title', '')}, segments={len(script.get('segments', []))}, "
            f"facts={len(facts)}"
        )
    except Exception as e:
        ctx.add_error("script", str(e), detail=str(e))
        ctx.log(f"错误: {str(e)}")

    script = state.get("script", {})
    detail = (
        f"输出: script.title='{script.get('title', 'N/A')[:50]}', "
        f"segments={len(script.get('segments', []))}, stages={len(state.get('stages', []))}"
    )
    ctx.log_end(detail)
    return ctx.finalize(state)


def _generate_script(
    topic: dict[str, Any],
    facts: list[dict[str, Any]],
    config: ScriptConfig,
    ctx: NodeContext,
) -> dict[str, Any]:
    api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = config.api_base or os.environ.get("OPENAI_API_BASE", "")
    preset = _preset_from_config(config)

    if not api_key or not api_base:
        ctx.log("未配置 LLM api_key/api_base，使用 deterministic 本地稿件生成器")
        return generate_deterministic_script(
            facts,
            preset,
            episode_id="",
            title=topic.get("title", "通勤早咖啡：今日新闻简报"),
        )

    facts_text = _build_facts_text(facts)
    prompt = _build_news_brief_prompt(topic, config, facts_text)
    messages = [
        {
            "role": "system",
            "content": "You are a professional news podcast editor. Return source-grounded JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    with LLMClient(
        api_base,
        api_key,
        config.llm_model,
        config.temperature,
        debug_mode=ctx.debug_mode,
    ) as client:
        ctx.log(f"LLM调用: model={config.llm_model}, timeout={config.timeout}s")
        response = client.call(messages, timeout=config.timeout, logs=ctx.logs)
        content = client.extract_content(response)

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return _normalize_script(parsed, topic, facts, config)
        except json.JSONDecodeError:
            ctx.log("JSON解析失败，使用 deterministic 降级输出")

    return generate_deterministic_script(
        facts,
        preset,
        episode_id="",
        title=topic.get("title", "通勤早咖啡：今日新闻简报"),
    )


def _preset_from_config(config: ScriptConfig) -> dict[str, Any]:
    preset = get_default_preset()
    preset.update(
        {
            "id": config.preset_id,
            "content_type": "news_brief",
            "num_hosts": 1,
            "target_duration_minutes": config.target_duration_minutes,
            "news_item_count": config.news_item_count,
            "tone": config.tone,
            "language": config.language,
        }
    )
    return preset
