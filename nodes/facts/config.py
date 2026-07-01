from pydantic import Field

from protocol.config_base import NodeConfigBase


class FactsConfig(NodeConfigBase):
    """Fact card generation configuration."""

    max_facts: int = Field(default=5, ge=1, le=20, description="最多生成事实卡片数量")
    selected_topic_count: int = Field(default=4, ge=1, le=10, description="默认早报条目数量")
    allow_cleaned_fallback: bool = Field(default=True, description="无 selected_materials 时是否 fallback 到 cleaned_contents")
