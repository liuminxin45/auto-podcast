"""
Research Node

深度研究、扩展信息、事实核查
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any, List
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class ResearchConfig(NodeConfig):
    """Research 节点配置"""
    
    enable_web_search: bool = False
    max_search_results: int = 5
    llm_model: str = "gpt-4o-mini"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "enable_web_search": False,
            "max_search_results": 5,
            "llm_model": "gpt-4o-mini"
        }


class ResearchNode(BaseNode):
    """研究节点"""
    
    def __init__(self, config: ResearchConfig):
        super().__init__(config)
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行研究"""
        self.log(state, "开始研究")
        
        try:
            researched = []
            
            for item in state.cleaned_contents:
                researched_item = {
                    **item,
                    "research_notes": "",
                    "key_points": [],
                    "verified": False
                }
                
                if self.config.enable_web_search:
                    researched_item["research_notes"] = self._research_topic(item.get("title", ""))
                
                researched.append(researched_item)
            
            state.researched_contents = researched
            self.log(state, f"研究完成，处理 {len(researched)} 条内容")
            
        except Exception as e:
            self.error(state, f"研究失败: {str(e)}", detail=str(e))
        
        return state
    
    def _research_topic(self, topic: str) -> str:
        """研究主题（预留实现）"""
        return f"Research notes for: {topic}"
