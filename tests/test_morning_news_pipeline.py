import json
import os
import wave
from pathlib import Path

from nodes.audio_postprocess.config import AudioPostprocessConfig
from nodes.audio_postprocess.node import run as audio_run
from nodes.facts.config import FactsConfig
from nodes.facts.node import run as facts_run
from nodes.publish.config import PublishConfig
from nodes.publish.node import run as publish_run
from nodes.script.config import ScriptConfig
from nodes.script.node import run as script_run
from nodes.tts.config import TTSConfig
from nodes.tts.node import run as tts_run
from protocol.morning_news import build_fact_cards, generate_deterministic_script
from protocol.presets import get_default_preset
from scripts.run_demo_news import run_demo_news
from tests.mock_data import create_base_state, create_mock_raw_contents


def test_default_preset_is_morning_news_brief():
    preset = get_default_preset()
    script_config = ScriptConfig()
    assert preset["id"] == "morning_news_brief"
    assert script_config.preset_id == "morning_news_brief"
    assert script_config.num_hosts == 1
    assert script_config.content_type == "news_brief"


def test_demo_data_generates_fact_cards():
    facts = build_fact_cards(create_mock_raw_contents(), limit=5)
    assert len(facts) >= 3
    assert facts[0]["id"] == "fact_001"
    assert {"title", "summary", "source_url", "claim", "confidence"} <= set(facts[0])


def test_script_segments_reference_fact_ids():
    facts = build_fact_cards(create_mock_raw_contents(), limit=3)
    script = generate_deterministic_script(facts, get_default_preset(), episode_id="test_ep")
    news_segments = [seg for seg in script["segments"] if seg["type"] == "news_item"]
    assert news_segments
    assert all(seg["source_fact_ids"] for seg in news_segments)


def test_script_node_generates_facts_and_structured_news_brief_without_api_key():
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_API_BASE", None)
    state = create_base_state()
    state["selected_topic"] = {"title": "通勤早咖啡"}
    state["selected_materials"] = create_mock_raw_contents()
    result = script_run(state, ScriptConfig())
    assert result["preset"]["id"] == "morning_news_brief"
    assert result["facts"]
    assert result["script"]["content_type"] == "news_brief"
    assert result["script"]["num_hosts"] == 1
    assert result["script"]["segments"]
    assert result["run_report"]["facts"]["total"] == len(result["facts"])


def test_facts_node_runs_before_script_in_primary_path():
    state = create_base_state()
    state["selected_topic"] = {"title": "通勤早咖啡"}
    state["selected_materials"] = create_mock_raw_contents()
    state = facts_run(state, FactsConfig(max_facts=4, selected_topic_count=4))
    assert state["facts"]
    result = script_run(state, ScriptConfig())
    assert result["_manifest"]["nodes"]["facts"]["status"] == "ok"
    assert result["_manifest"]["nodes"]["script"]["status"] == "ok"
    assert not any("compatibility fallback" in item for item in result.get("migration_warnings", []))


def test_tts_prefers_edited_script(tmp_path: Path):
    state = create_base_state()
    state["script"] = {
        "segments": [
            {
                "id": "seg_001",
                "type": "news_item",
                "title": "Generated",
                "text": "generated text should not be used",
                "source_fact_ids": ["fact_001"],
                "estimated_seconds": 6,
            }
        ]
    }
    state["edited_script"] = {
        "segments": [
            {
                "id": "seg_001",
                "type": "news_item",
                "title": "Edited",
                "text": "edited script text must be used",
                "source_fact_ids": ["fact_001"],
                "estimated_seconds": 6,
            }
        ]
    }
    result = tts_run(state, TTSConfig(engine="mock", output_dir=str(tmp_path)))
    assert result["tts_source"] == "edited_script"
    assert result["voice_segments"][0]["text"] == "edited script text must be used"
    assert Path(result["voice_segments"][0]["path"]).exists()


def test_audio_assembly_outputs_final_artifact(tmp_path: Path):
    seg_path = tmp_path / "seg_001.wav"
    _write_test_wav(seg_path)
    state = create_base_state()
    state["voice_segments"] = [{"segment_id": "seg_001", "path": str(seg_path)}]
    result = audio_run(
        state,
        AudioPostprocessConfig(output_dir=str(tmp_path), output_format="wav", final_basename="final"),
    )
    assert result["final_audio_path"]
    assert Path(result["final_audio_path"]).exists()
    assert Path(result["audio_report_path"]).exists()


def test_publish_package_outputs_feed_and_marks_local_preview(tmp_path: Path):
    audio_path = tmp_path / "final.wav"
    _write_test_wav(audio_path)
    state = create_base_state()
    state["final_audio_path"] = str(audio_path)
    state["script"] = {"title": "通勤早咖啡", "description": "demo"}
    result = publish_run(
        state,
        PublishConfig(
            local_base_dir=str(tmp_path / "dist" / "episodes"),
            rss_output_dir=str(tmp_path),
            public_base_url="",
        ),
    )
    assert Path(result["rss_path"]).exists()
    assert result["publish_status"]["local_preview_only"] is True
    assert result["run_report"]["warnings"]
    feed = Path(result["rss_path"]).read_text(encoding="utf-8")
    assert "local-preview only" in feed
    assert "file://" not in feed


def test_demo_news_e2e_runs_without_external_api_keys(tmp_path: Path):
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_API_BASE", None)
    output_dir = tmp_path / "output"
    state = run_demo_news(output_dir=output_dir, episode_id="test_demo_news")
    required = [
        "facts.json",
        "script.generated.json",
        "script.edited.json",
        "run_report.json",
        "episode.json",
        "feed.xml",
    ]
    for filename in required:
        assert (output_dir / filename).exists(), filename
    assert Path(state["final_audio_path"]).exists()
    report = json.loads((output_dir / "run_report.json").read_text(encoding="utf-8"))
    assert report["preset_id"] == "morning_news_brief"
    assert report["facts"]["total"] >= 3
    assert report["script"]["source_for_tts"] == "edited_script"
    assert state["publish_status"]["local_preview_only"] is True


def _write_test_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00" * 3200)
