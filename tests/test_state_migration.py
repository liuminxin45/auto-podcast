from protocol.migration import migrate_episode_state


def test_migration_adds_episode_run_v1_fields_and_migrates_legacy_dialogue():
    state = {
        "episode_id": "legacy_ep",
        "created_at": "2026-07-01T00:00:00",
        "script": {
            "title": "Legacy title",
            "description": "Legacy desc",
            "dialogue": [
                {"speaker": "Host A", "text": "开场文本"},
                {"speaker": "Host A", "text": "新闻文本"},
            ],
        },
        "stages": [],
        "selected_materials": [{"title": "source", "content": "body"}],
        "logs": [],
        "errors": [],
    }
    migrated = migrate_episode_state(state)
    assert migrated["schema_version"] == 1
    assert migrated["preset"]["id"] == "morning_news_brief"
    assert migrated["source_inputs"]
    assert migrated["edited_script"]["segments"]
    assert migrated["run_report"]["schema_validation"]["ok"] is True
    assert migrated["run_report"]["migration_warnings"]
