from pydantic import Field
from protocol.config_base import NodeConfigBase


class SourceSelectorConfig(NodeConfigBase):
    """Source selector node configuration."""
    
    source_type: str = Field(
        default="fetch",
        description="选择内容来源类型：fetch（自动抓取）或 manual（手动输入）"
    )
