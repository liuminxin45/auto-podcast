"""Product presets for PodFlow Studio's primary workflows."""

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_PRESET_ID = "morning_news_brief"


@dataclass(frozen=True)
class MorningNewsBriefPreset:
    """Default preset for a solo commute-friendly morning news brief."""

    id: str = DEFAULT_PRESET_ID
    content_type: str = "news_brief"
    num_hosts: int = 1
    target_duration_minutes: int = 6
    target_duration_minutes_range: str = "5-8"
    news_item_count: int = 4
    news_item_count_range: str = "3-5"
    tone: str = "clear, concise, commute-friendly"
    language: str = "zh-CN"


MORNING_NEWS_BRIEF_PRESET = MorningNewsBriefPreset()


def get_default_preset() -> dict[str, Any]:
    """Return the default preset as a plain dict for JSON state/config use."""

    return asdict(MORNING_NEWS_BRIEF_PRESET)
