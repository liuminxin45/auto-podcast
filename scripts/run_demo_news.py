"""Run the offline morning news brief demo without external API keys."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.audio_postprocess.config import AudioPostprocessConfig
from nodes.audio_postprocess.node import run as audio_run
from nodes.facts.config import FactsConfig
from nodes.facts.node import run as facts_run
from nodes.publish.config import PublishConfig
from nodes.publish.node import run as publish_run
from nodes.tts.config import TTSConfig
from nodes.tts.node import run as tts_run
from protocol.morning_news import (
    apply_manual_notes,
    build_run_report,
    generate_deterministic_script,
    script_to_stages,
    write_json,
)
from protocol.presets import get_default_preset


DEMO_DIR = ROOT / "examples" / "demo-news"
DEFAULT_OUTPUT_DIR = DEMO_DIR / "output"
DEFAULT_EPISODE_ID = "demo_morning_news_001"


def run_demo_news(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    episode_id: str = DEFAULT_EPISODE_ID,
) -> dict[str, Any]:
    input_dir = DEMO_DIR / "input"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "voice_segments").mkdir(parents=True, exist_ok=True)

    items = json.loads((input_dir / "sample-items.json").read_text(encoding="utf-8"))
    manual_notes = (input_dir / "manual-notes.md").read_text(encoding="utf-8").strip()
    preset = get_default_preset()
    state: dict[str, Any] = {
        "episode_id": episode_id,
        "created_at": datetime.now().isoformat(),
        "schema_version": 1,
        "preset": preset,
        "source_inputs": items,
        "fetch_contents": [],
        "manual_contents": [],
        "raw_contents": items,
        "cleaned_contents": items,
        "researched_contents": items,
        "facts": [],
        "selected_topic": {
            "title": "通勤早咖啡：今日新闻简报",
            "description": "面向通勤场景的单人新闻早报 demo",
            "keywords": ["通勤", "早报", "新闻"],
        },
        "selected_topics": [],
        "selected_materials": items,
        "script": {},
        "edited_script": {},
        "stages": [],
        "voice_segments": [],
        "audio_segments": [],
        "recording_segments": [],
        "final_audio_path": "",
        "audio_metadata": {},
        "audio_outputs": {},
        "audio_report_path": "",
        "cover_path": "",
        "intro_outro_paths": {},
        "review_summary": {},
        "storage_info": {},
        "rss_path": "",
        "publish_status": {},
        "publish_outputs": {},
        "subtitle_path": "",
        "run_report": {},
        "migration_warnings": [],
        "tts_source": "",
        "runtime_config": {},
        "errors": [],
        "logs": [],
    }

    state = facts_run(state, FactsConfig(max_facts=5, selected_topic_count=preset["news_item_count"]))
    facts = state["facts"]
    generated_script = generate_deterministic_script(
        facts,
        preset,
        episode_id=episode_id,
        title="通勤早咖啡：今日新闻简报",
    )
    edited_script = apply_manual_notes(generated_script, manual_notes)
    state["script"] = generated_script
    state["edited_script"] = edited_script
    state["stages"] = script_to_stages(edited_script)

    write_json(output_dir / "facts.json", facts)
    write_json(output_dir / "script.generated.json", generated_script)
    write_json(output_dir / "script.edited.json", edited_script)

    tts_config = _tts_config_from_env(output_dir / "voice_segments")
    state = tts_run(state, tts_config)
    if not state.get("audio_segments") and tts_config.engine != "mock":
        state["logs"].append("[Demo] Real TTS did not produce segments; falling back to mock TTS.")
        state = tts_run(state, TTSConfig(engine="mock", output_dir=str(output_dir / "voice_segments")))

    state = audio_run(
        state,
        AudioPostprocessConfig(
            output_dir=str(output_dir),
            output_format=os.environ.get("PODFLOW_DEMO_AUDIO_FORMAT", "mp3"),
            final_basename="final",
        ),
    )
    state = publish_run(
        state,
        PublishConfig(
            local_base_dir=str(output_dir / "dist" / "episodes"),
            rss_output_dir=str(output_dir),
            public_base_url=os.environ.get("PODFLOW_PUBLIC_BASE_URL", ""),
            podcast_title="通勤早咖啡",
            podcast_description="PodFlow Studio 单人新闻早报 demo",
            podcast_category="News",
        ),
    )

    write_json(output_dir / "episode.json", _episode_summary(state))
    write_json(output_dir / "run_report.json", build_run_report(state))
    return state


def _tts_config_from_env(output_dir: Path) -> TTSConfig:
    engine = os.environ.get("PODFLOW_DEMO_TTS_ENGINE", "mock").strip() or "mock"
    return TTSConfig(
        engine=engine,
        api_key=os.environ.get("PODFLOW_TTS_API_KEY") or os.environ.get("OPENAI_API_KEY", ""),
        api_base=os.environ.get("PODFLOW_TTS_API_BASE") or os.environ.get("OPENAI_API_BASE", ""),
        model=os.environ.get("PODFLOW_TTS_MODEL", "tts-1"),
        output_format="wav" if engine == "mock" else os.environ.get("PODFLOW_TTS_OUTPUT_FORMAT", "mp3"),
        output_dir=str(output_dir),
    )


def _episode_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": state.get("episode_id", ""),
        "preset": state.get("preset", {}),
        "facts": state.get("facts", []),
        "selected_topics": state.get("selected_topics", []),
        "script": state.get("script", {}),
        "edited_script": state.get("edited_script", {}),
        "audio_outputs": state.get("audio_outputs", {}),
        "publish_outputs": state.get("publish_outputs", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline PodFlow Studio morning news demo.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--episode-id", default=DEFAULT_EPISODE_ID, help="Episode id")
    args = parser.parse_args()

    state = run_demo_news(output_dir=Path(args.output), episode_id=args.episode_id)
    report = state.get("run_report", {})
    final_audio = state.get("final_audio_path", "")
    rss_path = state.get("rss_path", "")
    print("PodFlow Studio demo-news completed")
    print(f"episode_id: {state.get('episode_id')}")
    print(f"facts: {report.get('facts', {}).get('total', 0)}")
    print(f"segments: {report.get('script', {}).get('segments', 0)}")
    print(f"audio: {final_audio}")
    print(f"rss: {rss_path}")
    if state.get("publish_status", {}).get("local_preview_only"):
        print("warning: RSS is local-preview only, not publicly subscribable.")
    return 0 if final_audio and rss_path else 1


if __name__ == "__main__":
    raise SystemExit(main())
