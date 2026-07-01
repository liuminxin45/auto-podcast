from typing import Literal
from pydantic import Field
from protocol.config_base import NodeConfigBase, LLMConfigMixin
from protocol.presets import DEFAULT_PRESET_ID


class ScriptConfig(NodeConfigBase, LLMConfigMixin):
    """Script generation node configuration."""

    preset_id: Literal["morning_news_brief"] = Field(
        default=DEFAULT_PRESET_ID, description="默认产品预设"
    )
    content_type: Literal["story", "news_brief"] = Field(
        default="news_brief", description="文案类型（story/news_brief）"
    )

    target_duration_minutes: int = Field(
        default=6, ge=1, le=120, description="目标播客时长（分钟）"
    )
    dialogue_style: Literal["conversational", "formal", "casual"] = Field(
        default="formal", description="对话风格（conversational/formal/casual）"
    )
    num_hosts: int = Field(default=1, ge=1, le=5, description="主持人数量")
    news_item_count: int = Field(default=4, ge=1, le=20, description="新闻早报模式下的新闻条目数量")
    tone: str = Field(default="clear, concise, commute-friendly", description="默认语气")
    language: str = Field(default="zh-CN", description="稿件语言")
    require_approval: bool = Field(
        default=True,
        description="是否需要人工审批。开启后，脚本生成完成会暂停等待人工审批；关闭则由AI自动处理",
    )
    words_per_minute: int = Field(
        default=390,
        ge=50,
        le=600,
        description="语速（字/分钟），用于估算段落时长。中文TTS（edge-tts）实际语速约370-410字/分钟",
    )
