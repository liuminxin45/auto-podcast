from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PublishConfig:
    rss_output_dir: str = "out/rss"
    podcast_title: str = "AI Tech Podcast"
    podcast_description: str = "AI-generated tech podcast"
    podcast_author: str = "Auto-Podcast"
    podcast_language: str = "zh-CN"
    podcast_category: str = "Technology"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PublishConfig":
        defaults = {"rss_output_dir": "out/rss", "podcast_title": "AI Tech Podcast",
                    "podcast_description": "AI-generated tech podcast",
                    "podcast_author": "Auto-Podcast", "podcast_language": "zh-CN",
                    "podcast_category": "Technology"}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
