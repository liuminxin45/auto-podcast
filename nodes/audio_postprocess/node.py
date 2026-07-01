import wave
from pathlib import Path
from typing import Any

from nodes.audio_postprocess.config import AudioPostprocessConfig
from protocol.morning_news import build_run_report, write_json
from protocol.node_runner import NodeContext


def run(state: dict[str, Any], config: AudioPostprocessConfig = None) -> dict[str, Any]:
    config = config or AudioPostprocessConfig()
    ctx = NodeContext("AudioPostprocessNode", state)
    segments = _collect_segments(state)

    ctx.log_start(
        f"AudioAssembly starting | segments={len(segments)}, output={config.output_format}, "
        f"pause={config.segment_pause_ms}ms"
    )

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        if not segments:
            ctx.log("No audio segments to process")
            state["audio_outputs"] = {"status": "skipped", "reason": "no_audio_segments"}
            build_run_report(state)
            ctx.log_end("输出: final_audio_path=(empty)")
            return ctx.finalize(state)

        readable = [seg for seg in segments if Path(seg["path"]).exists()]
        missing = [seg["path"] for seg in segments if not Path(seg["path"]).exists()]
        if not readable:
            raise RuntimeError("No readable audio segments found.")

        requested_format = _normalize_format(config.output_format)
        output_path = Path(config.output_dir) / f"{config.final_basename}.{requested_format}"
        degraded = False
        operations = ["merge_voice_segments", f"segment_pause_{config.segment_pause_ms}ms"]

        try:
            final_path, duration_seconds = _assemble_with_pydub(
                readable, output_path, requested_format, config, operations
            )
        except Exception as pydub_error:
            degraded = True
            ctx.log(f"pydub/ffmpeg path unavailable, falling back to WAV assembly: {pydub_error}")
            final_path, duration_seconds = _assemble_wav_fallback(
                readable,
                Path(config.output_dir) / f"{config.final_basename}.wav",
                config.segment_pause_ms,
            )
            operations.append("fallback_wave_assembly")

        final_path = Path(final_path)
        audio_outputs = {
            "status": "ok",
            "final_audio_path": str(final_path),
            "format": final_path.suffix.lstrip("."),
            "requested_format": requested_format,
            "degraded": degraded,
            "duration_seconds": duration_seconds,
            "segments_count": len(readable),
            "source_segments": [seg["path"] for seg in readable],
            "missing_segments": missing,
            "operations": operations,
            "file_size": final_path.stat().st_size if final_path.exists() else 0,
        }
        state["final_audio_path"] = str(final_path)
        state["audio_metadata"] = {
            "duration_seconds": duration_seconds,
            "format": audio_outputs["format"],
            "segments_count": len(readable),
            "source_segments": audio_outputs["source_segments"],
            "file_size": audio_outputs["file_size"],
        }
        state["audio_outputs"] = audio_outputs
        audio_report_path = Path(config.output_dir) / "audio_report.json"
        write_json(audio_report_path, audio_outputs)
        state["audio_report_path"] = str(audio_report_path)
        build_run_report(state)
        ctx.log(f"AudioAssembly output: {final_path} ({duration_seconds:.1f}s)")
    except Exception as e:
        ctx.add_error("audio_postprocess", str(e), detail=str(e))
        state["audio_outputs"] = {"status": "error", "message": str(e)}
        build_run_report(state)

    ctx.log_end(f"输出: final_audio_path={state.get('final_audio_path', '')}")
    return ctx.finalize(state)


def _collect_segments(state: dict[str, Any]) -> list[dict[str, Any]]:
    voice_segments = state.get("voice_segments", [])
    if voice_segments:
        return [
            {"path": str(seg.get("path", "")), "segment_id": seg.get("segment_id", "")}
            for seg in voice_segments
            if isinstance(seg, dict) and seg.get("path")
        ]
    audio_segments = state.get("audio_segments", [])
    if audio_segments:
        return [{"path": _resolve_segment_path(item), "segment_id": ""} for item in audio_segments]
    recording_segments = state.get("recording_segments", [])
    return [
        {"path": str(seg.get("path", "")), "segment_id": seg.get("segmentId", "")}
        for seg in recording_segments
        if isinstance(seg, dict) and seg.get("path")
    ]


def _assemble_with_pydub(
    segments: list[dict[str, Any]],
    output_path: Path,
    output_format: str,
    config: AudioPostprocessConfig,
    operations: list[str],
) -> tuple[Path, float]:
    from pydub import AudioSegment, effects, silence

    combined = AudioSegment.empty()
    pause = AudioSegment.silent(duration=config.segment_pause_ms)
    for idx, segment in enumerate(segments):
        chunk = AudioSegment.from_file(segment["path"])
        if config.trim_silence:
            chunks = silence.split_on_silence(chunk, silence_thresh=chunk.dBFS - 16)
            if chunks:
                chunk = sum(chunks, AudioSegment.empty())
                operations.append("trim_silence")
        if config.normalize_loudness:
            chunk = effects.normalize(chunk)
        combined += chunk
        if idx < len(segments) - 1 and config.segment_pause_ms:
            combined += pause

    if config.normalize_loudness:
        combined = effects.normalize(combined)
        operations.append("normalize_loudness")

    combined.export(str(output_path), format=output_format)
    return output_path, len(combined) / 1000.0


def _assemble_wav_fallback(
    segments: list[dict[str, Any]],
    output_path: Path,
    segment_pause_ms: int,
) -> tuple[Path, float]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    params = None
    frames: list[bytes] = []
    total_frames = 0

    for segment in segments:
        with wave.open(segment["path"], "rb") as wav:
            current = wav.getparams()
            if params is None:
                params = current
            elif (
                current.nchannels != params.nchannels
                or current.sampwidth != params.sampwidth
                or current.framerate != params.framerate
            ):
                raise RuntimeError("WAV fallback requires matching channel count, width and rate.")
            data = wav.readframes(current.nframes)
            frames.append(data)
            total_frames += current.nframes
            pause_frames = int(current.framerate * (segment_pause_ms / 1000))
            if pause_frames:
                frames.append(b"\x00" * pause_frames * current.nchannels * current.sampwidth)
                total_frames += pause_frames

    if params is None:
        raise RuntimeError("No WAV segments available for fallback assembly.")

    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(params.nchannels)
        out.setsampwidth(params.sampwidth)
        out.setframerate(params.framerate)
        out.writeframes(b"".join(frames))

    return output_path, total_frames / params.framerate


def _resolve_segment_path(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("path") or item.get("file") or item.get("audio_path") or "")
    return ""


def _normalize_format(output_format: str) -> str:
    fmt = (output_format or "mp3").lower().lstrip(".")
    return fmt if fmt in {"mp3", "wav", "aac", "flac", "opus"} else "mp3"
