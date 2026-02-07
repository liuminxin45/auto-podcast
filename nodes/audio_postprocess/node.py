import os
from pathlib import Path
from typing import Dict, Any
from nodes.audio_postprocess.config import AudioPostprocessConfig


def run(state: Dict[str, Any], config: AudioPostprocessConfig = None) -> Dict[str, Any]:
    config = config or AudioPostprocessConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[AudioPostprocessNode] Starting audio postprocess")
    segments = state.get("audio_segments", [])

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        episode_id = state.get("episode_id", "unknown")

        if not segments:
            logs.append("[AudioPostprocessNode] No audio segments to process")
            state["logs"] = logs
            state["errors"] = errors
            return state

        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for seg_path in segments:
            if os.path.exists(seg_path):
                combined += AudioSegment.from_file(seg_path)

        output_path = os.path.join(config.output_dir, f"{episode_id}.{config.output_format}")
        combined.export(output_path, format=config.output_format)

        state["final_audio_path"] = output_path
        state["audio_metadata"] = {
            "duration_seconds": len(combined) / 1000.0,
            "format": config.output_format,
            "segments_count": len(segments),
        }
        logs.append(f"[AudioPostprocessNode] Output: {output_path} ({len(combined)/1000:.1f}s)")
    except Exception as e:
        errors.append({"node": "audio_postprocess", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state
