from typing import Dict, Any, List
from pydantic import Field
from protocol.config_base import NodeConfigBase


class FetchConfig(NodeConfigBase):
    sources: List[Dict[str, str]] = Field(
        default_factory=lambda: [{"type": "rss", "url": "https://hnrss.org/frontpage"}]
    )
    max_items_per_source: int = Field(default=10, ge=1, le=100)
    timeout: int = Field(default=30, ge=5, le=300)
    user_agent: str = Field(default="AutoPodcast/1.0")
