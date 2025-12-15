from __future__ import annotations

import json
from pathlib import Path


def publish_local(
    rendered_audio_path: Path,
    episodes_dir: Path,
    episode_date: str,
    title: str,
    shownotes: str,
    tags: list[str],
) -> Path:
    episodes_dir.mkdir(parents=True, exist_ok=True)

    final_path = episodes_dir / f"{episode_date}.published.mp3"
    if not final_path.exists():
        final_path.write_bytes(rendered_audio_path.read_bytes())

    meta_path = episodes_dir / f"{episode_date}.metadata.json"
    if not meta_path.exists():
        meta = {
            "episode_date": episode_date,
            "title": title,
            "tags": tags,
            "audio": str(final_path),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    notes_path = episodes_dir / f"{episode_date}.shownotes.md"
    if not notes_path.exists():
        notes_path.write_text(shownotes, encoding="utf-8")

    return final_path
