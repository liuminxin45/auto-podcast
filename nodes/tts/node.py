import asyncio
import json
import math
import os
import struct
import urllib.request
import wave
from pathlib import Path
from typing import Any

from nodes.tts.config import TTSConfig
from protocol.morning_news import active_script_for_tts, script_to_stages
from protocol.node_runner import NodeContext


def run(state: dict[str, Any], config: TTSConfig = None) -> dict[str, Any]:
    config = config or TTSConfig()
    ctx = NodeContext("TTSNode", state)

    tts_source, script = active_script_for_tts(state)
    stages = script_to_stages(script) if script else state.get("stages", [])
    state["tts_source"] = tts_source

    ctx.log_start(f"Starting TTS conversion | source={tts_source}, stages={len(stages)}")
    if not stages:
        state["audio_segments"] = []
        state["voice_segments"] = []
        ctx.log("无脚本段落，跳过 TTS 生成")
        ctx.log_end("输出: voice_segments=0")
        return ctx.finalize(state)

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        episode_id = state.get("episode_id", "unknown")

        ctx.log(f"使用引擎: {config.engine}")
        engine = (config.engine or "mock").lower()
        if engine in {"mock", "local-mock", "fallback"}:
            voice_segments = _synthesize_mock_all(stages, config, episode_id)
        elif engine in {"edge-tts", "edge", "openai-compatible", "openai", "openai-audio"}:
            voice_segments = asyncio.run(_synthesize_all(stages, config, episode_id))
        else:
            raise ValueError(f"Unsupported TTS engine: {config.engine}")
        state["voice_segments"] = voice_segments
        state["audio_segments"] = [segment["path"] for segment in voice_segments]
        ctx.log(f"音频片段生成完成: {len(voice_segments)} segments")
    except Exception as e:
        ctx.add_error("tts", str(e), detail=str(e))
        ctx.log(f"错误: {str(e)}")

    ctx.log_end(f"输出: voice_segments={len(state.get('voice_segments', []))}")
    return ctx.finalize(state)


async def _synthesize_all(stages: list[dict[str, Any]], config: TTSConfig, episode_id: str):
    segments = []
    for fallback_idx, stage in enumerate(stages):
        text = stage.get("text", "")
        if not text:
            continue
        idx_num = _segment_index(stage, fallback_idx)
        output_format = _normalize_output_format(config.output_format)
        filepath = os.path.join(config.output_dir, f"{episode_id}_{idx_num:03d}.{output_format}")
        voice = config.voice_mapping.get(stage.get("speaker", ""), config.default_voice)
        engine = (config.engine or "mock").lower()
        if engine in {"edge-tts", "edge"}:
            await _synthesize_edge_tts(text, voice, filepath, config)
        elif engine in {"openai-compatible", "openai", "openai-audio"}:
            _synthesize_openai_compatible(text, voice, filepath, config)
        else:
            raise ValueError(f"Unsupported TTS engine: {config.engine}")
        segments.append(_voice_segment(stage, filepath, engine, voice))
    return segments


def _synthesize_mock_all(
    stages: list[dict[str, Any]], config: TTSConfig, episode_id: str
) -> list[dict[str, Any]]:
    segments = []
    for fallback_idx, stage in enumerate(stages):
        text = stage.get("text", "")
        if not text:
            continue
        idx_num = _segment_index(stage, fallback_idx)
        filepath = os.path.join(config.output_dir, f"{episode_id}_{idx_num:03d}.wav")
        _write_mock_wav(filepath, text)
        segments.append(_voice_segment(stage, filepath, "mock", config.default_voice))
    return segments


def _voice_segment(
    stage: dict[str, Any],
    filepath: str,
    engine: str,
    voice: str,
) -> dict[str, Any]:
    return {
        "segment_id": stage.get("id") or f"seg_{_segment_index(stage, 0):03d}",
        "path": filepath,
        "text": stage.get("text", ""),
        "speaker": stage.get("speaker", "Host A"),
        "source_fact_ids": stage.get("source_fact_ids", []),
        "engine": engine,
        "voice": voice,
    }


def _segment_index(stage: dict[str, Any], fallback_idx: int) -> int:
    idx = stage.get("index", stage.get("order", fallback_idx))
    try:
        return int(idx) + 1 if int(idx) == fallback_idx else int(idx)
    except (TypeError, ValueError):
        return fallback_idx + 1


def _normalize_output_format(output_format: str) -> str:
    fmt = (output_format or "mp3").lower().lstrip(".")
    return fmt if fmt in {"mp3", "wav", "opus", "aac", "flac"} else "mp3"


async def _synthesize_edge_tts(text: str, voice: str, filepath: str, config: TTSConfig) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=config.rate, volume=config.volume)
    await communicate.save(filepath)


def _synthesize_openai_compatible(text: str, voice: str, filepath: str, config: TTSConfig) -> None:
    api_key = (config.api_key or "").strip()
    api_base = (config.api_base or "").strip().rstrip("/")
    model = (config.model or "").strip()
    if not api_key or not api_base or not model:
        raise ValueError("OpenAI-compatible TTS requires api_key, api_base and model")

    output_format = _normalize_output_format(config.output_format)
    payload = {
        "model": model,
        "voice": voice or config.default_voice or "alloy",
        "input": text,
        "response_format": output_format,
    }
    req = urllib.request.Request(
        f"{api_base}/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=config.timeout_seconds) as response:
        body = response.read()
    Path(filepath).write_bytes(body)


def _write_mock_wav(filepath: str, text: str) -> None:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16_000
    duration = min(3.0, max(0.45, len(text) / 85.0))
    total_frames = int(sample_rate * duration)
    frequency = 440.0
    amplitude = 1200
    with wave.open(filepath, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(total_frames):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * (i / sample_rate)))
            wav.writeframes(struct.pack("<h", sample))
