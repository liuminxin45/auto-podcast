"""
Stages Node

脚本分段、角色分配、时长优化
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class StagesConfig(NodeConfig):
    """Stages 节点配置"""
    
    words_per_minute: int = 150
    max_segment_duration: int = 120
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "words_per_minute": 150,
            "max_segment_duration": 120
        }


class StagesNode(BaseNode):
    """分段节点"""
    
    def __init__(self, config: StagesConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行分段"""
        self.log(state, "开始分段处理")
        
        try:
            script = state.script
            dialogue = script.get("dialogue", [])
            
            if not dialogue:
                self.error(state, "脚本中没有对话内容")
                return state
            
            stages = []
            
            for idx, item in enumerate(dialogue):
                speaker = item.get("speaker", "未知")
                text = item.get("text", "")
                
                word_count = len(text.split())
                duration = word_count / self.config.words_per_minute * 60
                
                stages.append({
                    "order": idx,
                    "speaker": speaker,
                    "text": text,
                    "word_count": word_count,
                    "duration_seconds": round(duration, 2)
                })
            
            state.stages = stages
            total_duration = sum(s["duration_seconds"] for s in stages)
            self.log(state, f"分段完成，共 {len(stages)} 段，预计时长 {total_duration/60:.1f} 分钟")
            
        except Exception as e:
            self.error(state, f"分段失败: {str(e)}", detail=str(e))
        
        return state
