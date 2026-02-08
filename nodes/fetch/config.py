from typing import List
from pydantic import Field
from protocol.config_base import NodeConfigBase


class FetchConfig(NodeConfigBase):
    """Fetch node configuration."""
    
    enabled_sources: List[str] = Field(
        default_factory=lambda: ["hackernews"],
        description="启用的数据源列表（文件名，不含.py扩展名）。勾选的数据源会被执行。"
    )
