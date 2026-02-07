from typing import Dict, Any
from pydantic import Field
from protocol.config_base import NodeConfigBase, LLMConfigMixin


class ScriptConfig(NodeConfigBase, LLMConfigMixin):
    llm_model: str = Field(default="gpt-4o")
    target_duration_minutes: int = Field(default=15, ge=1, le=120)
    dialogue_style: str = Field(default="conversational")
    num_hosts: int = Field(default=2, ge=1, le=5)
