"""Typed EpisodeRun schema models for the morning news primary path."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from protocol.presets import get_default_preset


SCHEMA_VERSION = 1


class FactCardModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    summary: str
    source_title: str = ""
    source_url: str = ""
    published_at: str = ""
    claim: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    used_in_segments: list[str] = Field(default_factory=list)


class ScriptSegmentModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: Literal["opening", "news_item", "context", "transition", "closing", "custom"]
    title: str = ""
    text: str
    source_fact_ids: list[str] = Field(default_factory=list)
    estimated_seconds: int = 0
    speaker: str = "Host A"


class ScriptModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str = ""
    description: str = ""
    content_type: str = "news_brief"
    preset_id: str = "morning_news_brief"
    num_hosts: int = 1
    language: str = "zh-CN"
    segments: list[ScriptSegmentModel] = Field(default_factory=list)


class AudioOutputsModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = ""
    final_audio_path: str = ""
    format: str = ""
    requested_format: str = ""
    degraded: bool = False
    duration_seconds: float = 0.0
    segments_count: int = 0
    source_segments: list[str] = Field(default_factory=list)
    missing_segments: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    file_size: int = 0


class RssValidationModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    enclosure_url: str = ""
    local_preview_only: bool = True


class PublishOutputsModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    episode_dir: str = ""
    audio_path: str = ""
    episode_json: str = ""
    feed_xml: str = ""
    run_report_json: str = ""
    enclosure_url: str = ""
    local_preview_only: bool = True
    rss_validation: RssValidationModel = Field(default_factory=RssValidationModel)


class RunReportModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    episode_id: str = ""
    preset_id: str = "morning_news_brief"
    facts: dict[str, Any] = Field(default_factory=dict)
    script: dict[str, Any] = Field(default_factory=dict)
    audio: dict[str, Any] = Field(default_factory=dict)
    publish: dict[str, Any] = Field(default_factory=dict)
    schema_validation: dict[str, Any] = Field(default_factory=dict)
    rss_validation: dict[str, Any] = Field(default_factory=dict)
    migration_warnings: list[str] = Field(default_factory=list)
    tts_live_validation: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class EpisodeRunModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal[1] = SCHEMA_VERSION
    episode_id: str
    preset: dict[str, Any] = Field(default_factory=get_default_preset)
    source_inputs: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[FactCardModel] = Field(default_factory=list)
    selected_topics: list[dict[str, Any]] = Field(default_factory=list)
    script: ScriptModel = Field(default_factory=ScriptModel)
    edited_script: ScriptModel = Field(default_factory=ScriptModel)
    voice_segments: list[dict[str, Any]] = Field(default_factory=list)
    audio_outputs: AudioOutputsModel = Field(default_factory=AudioOutputsModel)
    publish_outputs: PublishOutputsModel = Field(default_factory=PublishOutputsModel)
    run_report: RunReportModel = Field(default_factory=RunReportModel)


def validate_episode_run_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate an EpisodeRun-like dict without requiring unrelated workflow keys."""

    try:
        EpisodeRunModel.model_validate(payload)
        return True, []
    except Exception as exc:
        return False, [str(exc)]
