"""Morning news brief domain model and deterministic local pipeline helpers."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from protocol.presets import get_default_preset


CHARS_PER_SECOND = 6.5


@dataclass
class FactCard:
    id: str
    title: str
    summary: str
    source_title: str
    source_url: str
    published_at: str
    claim: str
    confidence: str
    used_in_segments: list[str] = field(default_factory=list)


@dataclass
class ScriptSegment:
    id: str
    type: str
    title: str
    text: str
    source_fact_ids: list[str]
    estimated_seconds: int
    speaker: str = "Host A"


@dataclass
class EpisodeRun:
    episode_id: str
    preset: dict[str, Any]
    source_inputs: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    selected_topics: list[dict[str, Any]] = field(default_factory=list)
    script: dict[str, Any] = field(default_factory=dict)
    edited_script: dict[str, Any] = field(default_factory=dict)
    voice_segments: list[dict[str, Any]] = field(default_factory=list)
    audio_outputs: dict[str, Any] = field(default_factory=dict)
    publish_outputs: dict[str, Any] = field(default_factory=dict)
    run_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_fact_cards(source_inputs: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Convert normalized news inputs into deduplicated FactCard dicts."""

    facts: list[FactCard] = []
    seen: set[str] = set()
    for item in source_inputs:
        if len(facts) >= limit:
            break
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title") or item.get("headline") or "Untitled")
        body = _clean_text(item.get("summary") or item.get("content") or item.get("description") or "")
        if not title or not body:
            continue
        dedup_key = _dedup_key(title, item.get("url", ""))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        source_url = str(item.get("url") or item.get("source_url") or "")
        source_title = str(item.get("source_title") or item.get("source_name") or item.get("source") or title)
        published_at = str(item.get("published_at") or item.get("published") or "")
        claim = _first_sentence(body, max_chars=180)
        confidence = "high" if source_url and published_at else "medium" if source_url else "low"
        facts.append(
            FactCard(
                id=f"fact_{len(facts) + 1:03d}",
                title=title,
                summary=_truncate(body, 260),
                source_title=source_title,
                source_url=source_url,
                published_at=published_at,
                claim=claim,
                confidence=confidence,
            )
        )
    return [asdict(fact) for fact in facts]


def select_news_topics(facts: list[dict[str, Any]], count: int | None = None) -> list[dict[str, Any]]:
    preset = get_default_preset()
    selected_count = count or preset["news_item_count"]
    return [
        {
            "id": f"topic_{idx + 1:03d}",
            "title": fact.get("title", ""),
            "fact_id": fact.get("id", ""),
        }
        for idx, fact in enumerate(facts[:selected_count])
    ]


def generate_deterministic_script(
    facts: list[dict[str, Any]],
    preset: dict[str, Any] | None = None,
    *,
    episode_id: str = "",
    title: str = "通勤早咖啡：今日新闻简报",
) -> dict[str, Any]:
    """Generate a source-grounded solo news script without an external model."""

    preset = preset or get_default_preset()
    selected = facts[: int(preset.get("news_item_count", 4))]
    source_ids = [str(f.get("id", "")) for f in selected if f.get("id")]
    if not selected:
        return _script_dict(title, preset, [], episode_id, generated_by="deterministic_mock")

    segments: list[dict[str, Any]] = [
        _segment(
            "seg_001",
            "opening",
            "开场",
            f"早上好，欢迎来到通勤早咖啡。今天用几分钟梳理 {len(selected)} 条值得关注的新闻，先给结论，再说影响。",
            source_ids,
        )
    ]

    for idx, fact in enumerate(selected, start=1):
        text = (
            f"第 {idx} 条，{fact.get('title', '这条新闻')}。"
            f"{fact.get('claim') or fact.get('summary', '')} "
            f"这件事的重点是：{_impact_sentence(fact)}"
        )
        segments.append(
            _segment(
                f"seg_{idx + 1:03d}",
                "news_item",
                str(fact.get("title", f"新闻 {idx}")),
                text,
                [str(fact.get("id", ""))] if fact.get("id") else [],
            )
        )

    segments.append(
        _segment(
            f"seg_{len(segments) + 1:03d}",
            "closing",
            "收束",
            "以上就是今天的单人新闻早报。你可以在发布前继续编辑稿件、替换单段录音，确认无误后再导出 RSS 或发布包。",
            source_ids,
        )
    )

    updated_facts = _mark_used_facts(selected, segments)
    script = _script_dict(title, preset, segments, episode_id, generated_by="deterministic_mock")
    script["facts_snapshot"] = updated_facts
    return script


def apply_manual_notes(script: dict[str, Any], manual_notes: str = "") -> dict[str, Any]:
    """Create an edited script version that proves manual edits feed production."""

    edited = copy.deepcopy(script)
    edited["id"] = f"{script.get('id', 'script')}_edited"
    edited["edited_from"] = script.get("id", "script.generated")
    edited["edit_mode"] = "manual_notes"
    note = _clean_text(manual_notes)
    if note:
        edited["manual_notes"] = note
        for segment in edited.get("segments", []):
            if segment.get("type") == "opening":
                segment["text"] = f"{segment.get('text', '')} {note}"
                segment["estimated_seconds"] = estimate_seconds(segment["text"])
                break
    _sync_script_compat_fields(edited)
    return edited


def script_to_stages(script: dict[str, Any]) -> list[dict[str, Any]]:
    stages = []
    for idx, segment in enumerate(script.get("segments", [])):
        if not isinstance(segment, dict) or not segment.get("text"):
            continue
        stages.append(
            {
                "id": segment.get("id", f"seg_{idx + 1:03d}"),
                "order": idx,
                "speaker": segment.get("speaker", "Host A"),
                "label": segment.get("title", ""),
                "text": segment.get("text", ""),
                "source_fact_ids": segment.get("source_fact_ids", []),
                "estimated_duration": segment.get("estimated_seconds")
                or estimate_seconds(segment.get("text", "")),
            }
        )
    return stages


def active_script_for_tts(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    edited = state.get("edited_script")
    if isinstance(edited, dict) and edited.get("segments"):
        return "edited_script", edited
    script = state.get("script")
    if isinstance(script, dict) and script.get("segments"):
        return "script", script
    return "stages", {}


def build_run_report(state: dict[str, Any]) -> dict[str, Any]:
    facts = state.get("facts", [])
    script_name, active_script = active_script_for_tts(state)
    segments = active_script.get("segments", []) if active_script else state.get("stages", [])
    used_fact_ids = {
        fact_id
        for segment in segments
        if isinstance(segment, dict)
        for fact_id in segment.get("source_fact_ids", [])
    }
    all_fact_ids = {fact.get("id") for fact in facts if isinstance(fact, dict)}
    warnings: list[dict[str, Any]] = []
    for segment in segments:
        if isinstance(segment, dict) and not segment.get("source_fact_ids"):
            warnings.append(
                {
                    "code": "segment_without_source",
                    "segment_id": segment.get("id", ""),
                    "message": "Script segment has no source_fact_ids.",
                }
            )
    publish_status = state.get("publish_status", {})
    if publish_status.get("local_preview_only"):
        warnings.append(
            {
                "code": "rss_local_preview_only",
                "message": "RSS is local-preview only, not publicly subscribable.",
            }
        )

    report = {
        "episode_id": state.get("episode_id", ""),
        "preset_id": state.get("preset", {}).get("id", "morning_news_brief"),
        "facts": {
            "total": len(facts),
            "used": len(used_fact_ids),
            "unused": len(all_fact_ids - used_fact_ids),
        },
        "script": {
            "source_for_tts": script_name,
            "segments": len(segments),
            "segment_ids_without_sources": [
                warning.get("segment_id") for warning in warnings if warning.get("code") == "segment_without_source"
            ],
        },
        "audio": state.get("audio_outputs", {}),
        "publish": state.get("publish_outputs", {}),
        "schema_validation": state.get("run_report", {}).get("schema_validation", {}),
        "rss_validation": state.get("publish_outputs", {}).get("rss_validation", {})
        or state.get("run_report", {}).get("rss_validation", {}),
        "migration_warnings": state.get("migration_warnings", []),
        "tts_live_validation": state.get("run_report", {}).get("tts_live_validation", {}),
        "warnings": warnings,
    }
    state["run_report"] = report
    return report


def estimate_seconds(text: str) -> int:
    return max(6, round(len(_clean_text(text)) / CHARS_PER_SECOND))


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _script_dict(
    title: str,
    preset: dict[str, Any],
    segments: list[dict[str, Any]],
    episode_id: str,
    *,
    generated_by: str,
) -> dict[str, Any]:
    script = {
        "id": f"{episode_id or 'episode'}_script_generated",
        "title": title,
        "description": "单人新闻早报，面向通勤路上的快速收听。",
        "content_type": "news_brief",
        "preset_id": preset.get("id", "morning_news_brief"),
        "num_hosts": 1,
        "language": preset.get("language", "zh-CN"),
        "segments": segments,
        "generated_by": generated_by,
    }
    _sync_script_compat_fields(script)
    return script


def _sync_script_compat_fields(script: dict[str, Any]) -> None:
    segments = script.get("segments", [])
    script["sections"] = [
        {
            "id": segment.get("id"),
            "type": segment.get("type", "custom"),
            "label": segment.get("title", ""),
            "speaker": segment.get("speaker", "Host A"),
            "text": segment.get("text", ""),
            "source_fact_ids": segment.get("source_fact_ids", []),
            "estimated_seconds": segment.get("estimated_seconds", 0),
        }
        for segment in segments
        if isinstance(segment, dict)
    ]
    script["dialogue"] = [
        {"speaker": section.get("speaker", "Host A"), "text": section.get("text", "")}
        for section in script["sections"]
        if section.get("text")
    ]


def _segment(
    segment_id: str,
    segment_type: str,
    title: str,
    text: str,
    source_fact_ids: list[str],
) -> dict[str, Any]:
    return asdict(
        ScriptSegment(
            id=segment_id,
            type=segment_type,
            title=title,
            text=_clean_text(text),
            source_fact_ids=[fact_id for fact_id in source_fact_ids if fact_id],
            estimated_seconds=estimate_seconds(text),
        )
    )


def _mark_used_facts(facts: list[dict[str, Any]], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated = copy.deepcopy(facts)
    by_id = {fact.get("id"): fact for fact in updated}
    for segment in segments:
        for fact_id in segment.get("source_fact_ids", []):
            fact = by_id.get(fact_id)
            if fact is not None:
                fact.setdefault("used_in_segments", [])
                if segment.get("id") not in fact["used_in_segments"]:
                    fact["used_in_segments"].append(segment.get("id"))
    return updated


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _truncate(value: str, max_chars: int) -> str:
    text = _clean_text(value)
    return text if len(text) <= max_chars else f"{text[: max_chars - 1]}…"


def _first_sentence(value: str, max_chars: int) -> str:
    text = _clean_text(value)
    match = re.search(r"(.+?[。！？.!?])", text)
    sentence = match.group(1) if match else text
    return _truncate(sentence, max_chars)


def _dedup_key(title: str, url: Any) -> str:
    normalized_title = re.sub(r"\W+", "", title.lower())
    return str(url or normalized_title)


def _impact_sentence(fact: dict[str, Any]) -> str:
    confidence = fact.get("confidence", "medium")
    if confidence == "high":
        return "它有明确来源和时间，可以作为本期的主信息点。"
    if confidence == "medium":
        return "来源信息基本可追踪，但发布前仍建议核对细节。"
    return "来源不足，发布前需要人工确认。"
