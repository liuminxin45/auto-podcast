import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any
from nodes.store.config import StoreConfig


def run(state: Dict[str, Any], config: StoreConfig = None) -> Dict[str, Any]:
    config = config or StoreConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[StoreNode] Starting storage")
    episode_id = state.get("episode_id", "unknown")

    try:
        episode_dir = os.path.join(config.local_base_dir, episode_id)
        Path(episode_dir).mkdir(parents=True, exist_ok=True)

        audio_path = state.get("final_audio_path", "")
        if audio_path and os.path.exists(audio_path):
            dest = os.path.join(episode_dir, os.path.basename(audio_path))
            shutil.copy2(audio_path, dest)

        cover_path = state.get("cover_path", "")
        if cover_path and os.path.exists(cover_path):
            dest = os.path.join(episode_dir, os.path.basename(cover_path))
            shutil.copy2(cover_path, dest)

        if config.generate_metadata:
            meta = {
                "episode_id": episode_id,
                "title": state.get("script", {}).get("title", ""),
                "description": state.get("script", {}).get("description", ""),
                "audio_metadata": state.get("audio_metadata", {}),
                "created_at": state.get("created_at", ""),
            }
            meta_path = os.path.join(episode_dir, "metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        state["storage_info"] = {"type": config.storage_type, "base_dir": episode_dir}
        logs.append(f"[StoreNode] Stored: {episode_dir}")
    except Exception as e:
        errors.append({"node": "store", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state
