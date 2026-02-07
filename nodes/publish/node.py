import os
from pathlib import Path
from typing import Dict, Any
from nodes.publish.config import PublishConfig


def run(state: Dict[str, Any], config: PublishConfig = None) -> Dict[str, Any]:
    config = config or PublishConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[PublishNode] Starting publish")

    try:
        Path(config.rss_output_dir).mkdir(parents=True, exist_ok=True)

        rss_path = os.path.join(config.rss_output_dir, "feed.xml")
        rss_content = _generate_rss(state, config)

        with open(rss_path, "w", encoding="utf-8") as f:
            f.write(rss_content)

        state["rss_path"] = rss_path
        state["publish_status"] = {"rss_generated": True, "rss_path": rss_path}
        logs.append(f"[PublishNode] RSS: {rss_path}")
    except Exception as e:
        errors.append({"node": "publish", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state


def _generate_rss(state: Dict, config: PublishConfig) -> str:
    script = state.get("script", {})
    title = script.get("title", config.podcast_title)
    desc = script.get("description", config.podcast_description)
    audio_path = state.get("final_audio_path", "")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{config.podcast_title}</title>
    <description>{config.podcast_description}</description>
    <language>{config.podcast_language}</language>
    <itunes:author>{config.podcast_author}</itunes:author>
    <itunes:category text="{config.podcast_category}"/>
    <item>
      <title>{title}</title>
      <description>{desc}</description>
      <enclosure url="{audio_path}" type="audio/mpeg"/>
    </item>
  </channel>
</rss>"""
