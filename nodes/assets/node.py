import os
from pathlib import Path
from typing import Dict, Any
from nodes.assets.config import AssetsConfig


def run(state: Dict[str, Any], config: AssetsConfig = None) -> Dict[str, Any]:
    config = config or AssetsConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[AssetsNode] Starting asset generation")

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        episode_id = state.get("episode_id", "unknown")

        if config.generate_cover:
            cover_path = _generate_cover(episode_id, state, config)
            state["cover_path"] = cover_path
            logs.append(f"[AssetsNode] Cover: {cover_path}")

        logs.append("[AssetsNode] Assets done")
    except Exception as e:
        errors.append({"node": "assets", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state


def _generate_cover(episode_id: str, state: Dict, config: AssetsConfig) -> str:
    from PIL import Image, ImageDraw, ImageFont

    w, h = config.cover_size
    img = Image.new("RGB", (w, h), color=(30, 30, 60))
    draw = ImageDraw.Draw(img)

    title = state.get("script", {}).get("title", state.get("selected_topic", {}).get("title", "Podcast"))

    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except (IOError, OSError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), title, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2), title, fill="white", font=font)

    cover_path = os.path.join(config.output_dir, f"{episode_id}_cover.png")
    img.save(cover_path)
    return cover_path
