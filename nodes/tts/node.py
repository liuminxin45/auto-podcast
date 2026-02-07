import os
import asyncio
from pathlib import Path
from typing import Dict, Any
from nodes.tts.config import TTSConfig


def run(state: Dict[str, Any], config: TTSConfig = None) -> Dict[str, Any]:
    config = config or TTSConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[TTSNode] Starting TTS conversion")
    stages = state.get("stages", [])

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        episode_id = state.get("episode_id", "unknown")
        segments = asyncio.run(_synthesize_all(stages, config, episode_id))
        state["audio_segments"] = segments
        logs.append(f"[TTSNode] Generated {len(segments)} audio segments")
    except Exception as e:
        errors.append({"node": "tts", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state


async def _synthesize_all(stages, config, episode_id):
    import edge_tts
    segments = []
    for stage in stages:
        speaker = stage.get("speaker", "")
        text = stage.get("text", "")
        idx = stage.get("index", 0)
        if not text:
            continue

        voice = config.voice_mapping.get(speaker, config.default_voice)
        filename = f"{episode_id}_{idx:03d}.mp3"
        filepath = os.path.join(config.output_dir, filename)

        communicate = edge_tts.Communicate(text, voice, rate=config.rate, volume=config.volume)
        await communicate.save(filepath)
        segments.append(filepath)

    return segments
