"""
Subtitles Node (占位节点，默认禁用)

生成字幕（当前播客不需要字幕，预留未来扩展）
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class SubtitlesConfig(NodeConfig):
    """Subtitles 节点配置"""
    
    enabled: bool = False
    output_format: str = "srt"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "enabled": False,
            "output_format": "srt"
        }


class SubtitlesNode(BaseNode):
    """字幕生成节点（占位）"""
    
    def __init__(self, config: SubtitlesConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行字幕生成（当前跳过）"""
        if not self.config.enabled:
            self.log(state, "字幕生成已禁用，跳过")
            return state
        
        self.log(state, "字幕生成功能暂未实现")
        return state
