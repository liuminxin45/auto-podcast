import json
from pathlib import Path

from protocol.episode_models import SCHEMA_VERSION, validate_episode_run_payload
from tests.mock_data import create_base_state


def test_episode_run_schema_file_requires_primary_contract_fields():
    schema_path = Path(__file__).resolve().parents[1] / "protocol" / "schemas" / "episode_run.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    required = set(schema["required"])
    assert {
        "schema_version",
        "episode_id",
        "preset",
        "source_inputs",
        "facts",
        "selected_topics",
        "script",
        "edited_script",
        "voice_segments",
        "audio_outputs",
        "publish_outputs",
        "run_report",
    } <= required


def test_episode_run_payload_validates_with_model():
    state = create_base_state()
    ok, errors = validate_episode_run_payload(state)
    assert ok, errors
