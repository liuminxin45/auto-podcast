"""State migration helpers for EpisodeRun schema v1."""

from __future__ import annotations

from typing import Any

from protocol.episode_models import SCHEMA_VERSION, validate_episode_run_payload
from protocol.morning_news import estimate_seconds, script_to_stages
from protocol.presets import get_default_preset


def migrate_episode_state(state: dict[str, Any]) -> dict[str, Any]:
    """Mutate and return workflow state with EpisodeRun v1 fields present."""

    warnings = state.setdefault("migration_warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        state["migration_warnings"] = warnings

    if state.get("schema_version") != SCHEMA_VERSION:
        if state.get("schema_version") is not None:
            warnings.append(f"schema_version upgraded from {state.get('schema_version')} to {SCHEMA_VERSION}")
        state["schema_version"] = SCHEMA_VERSION

    state.setdefault("preset", get_default_preset())
    state.setdefault("source_inputs", [])
    state.setdefault("facts", [])
    state.setdefault("selected_topics", [])
    state.setdefault("script", {})
    state.setdefault("edited_script", {})
    state.setdefault("voice_segments", [])
    state.setdefault("audio_outputs", {})
    state.setdefault("publish_outputs", {})
    state.setdefault("run_report", {})
    state.setdefault("audio_report_path", "")
    state.setdefault("tts_source", "")

    if not state.get("source_inputs"):
        source_inputs = (
            state.get("selected_materials")
            or state.get("cleaned_contents")
            or state.get("raw_contents")
            or state.get("fetch_contents")
            or state.get("manual_contents")
            or []
        )
        state["source_inputs"] = source_inputs if isinstance(source_inputs, list) else []

    edited_script = state.get("edited_script")
    if not isinstance(edited_script, dict):
        edited_script = {}
        state["edited_script"] = edited_script

    if not edited_script.get("segments"):
        migrated = _migrate_legacy_script_to_segments(state)
        if migrated:
            state["edited_script"] = migrated
            state["stages"] = script_to_stages(migrated)
            warnings.append("legacy script.dialogue/stages migrated to edited_script.segments")

    episode_payload = _episode_payload_for_validation(state)
    ok, errors = validate_episode_run_payload(episode_payload)
    report = state.setdefault("run_report", {})
    if isinstance(report, dict):
        report["schema_validation"] = {"ok": ok, "errors": errors, "schema_version": SCHEMA_VERSION}
        report["migration_warnings"] = warnings
    return state


def _migrate_legacy_script_to_segments(state: dict[str, Any]) -> dict[str, Any]:
    script = state.get("script") if isinstance(state.get("script"), dict) else {}
    stages = state.get("stages") if isinstance(state.get("stages"), list) else []
    dialogue = script.get("dialogue") if isinstance(script.get("dialogue"), list) else []

    source = stages or [
        {
            "id": f"seg_{idx + 1:03d}",
            "type": "news_item",
            "title": "",
            "text": line.get("text", ""),
            "speaker": line.get("speaker", "Host A"),
        }
        for idx, line in enumerate(dialogue)
        if isinstance(line, dict)
    ]
    if not source:
        return {}

    segments = []
    for idx, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        segment_type = item.get("type") or ("opening" if idx == 0 else "closing" if idx == len(source) - 1 else "news_item")
        if segment_type not in {"opening", "news_item", "context", "transition", "closing", "custom"}:
            segment_type = "news_item"
        segments.append(
            {
                "id": str(item.get("id") or f"seg_{idx + 1:03d}"),
                "type": segment_type,
                "title": str(item.get("title") or item.get("label") or ""),
                "text": text,
                "source_fact_ids": list(item.get("source_fact_ids") or []),
                "estimated_seconds": int(item.get("estimated_seconds") or item.get("estimated_duration") or estimate_seconds(text)),
                "speaker": str(item.get("speaker") or "Host A"),
            }
        )

    return {
        "id": f"{state.get('episode_id', 'episode')}_edited_migrated",
        "title": script.get("title", state.get("selected_topic", {}).get("title", "")),
        "description": script.get("description", state.get("selected_topic", {}).get("description", "")),
        "content_type": "news_brief",
        "preset_id": "morning_news_brief",
        "num_hosts": 1,
        "language": "zh-CN",
        "segments": segments,
        "edited_from": script.get("id", "legacy_script"),
        "edit_mode": "migration",
    }


def _episode_payload_for_validation(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": state.get("schema_version", SCHEMA_VERSION),
        "episode_id": state.get("episode_id", ""),
        "preset": state.get("preset", {}),
        "source_inputs": state.get("source_inputs", []),
        "facts": state.get("facts", []),
        "selected_topics": state.get("selected_topics", []),
        "script": state.get("script", {}),
        "edited_script": state.get("edited_script", {}),
        "voice_segments": state.get("voice_segments", []),
        "audio_outputs": state.get("audio_outputs", {}),
        "publish_outputs": state.get("publish_outputs", {}),
        "run_report": state.get("run_report", {}),
    }
