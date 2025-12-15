import subprocess
from pathlib import Path


class AudioRenderError(RuntimeError):
    pass


def render_episode_audio(
    intro_path: Path,
    main_path: Path,
    outro_path: Path,
    bgm_path: Path,
    bgm_volume: float,
    out_path: Path,
    timeout_seconds: int,
) -> None:
    for p in [intro_path, main_path, outro_path, bgm_path]:
        if not p.exists():
            raise AudioRenderError(f"missing audio asset: {p}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter strategy:
    # - concat intro+main+outro
    # - mix in bgm at low volume
    # - loudness normalization
    filter_complex = (
        f"[3:a]volume={bgm_volume}[bg];"
        "[0:a][1:a][2:a]concat=n=3:v=0:a=1[voice];"
        "[voice][bg]amix=inputs=2:duration=first:dropout_transition=3[mixed];"
        "[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(intro_path),
        "-i",
        str(main_path),
        "-i",
        str(outro_path),
        "-i",
        str(bgm_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "3",
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as e:
        raise AudioRenderError("ffmpeg timeout") from e
    except subprocess.CalledProcessError as e:
        raise AudioRenderError("ffmpeg failed") from e
