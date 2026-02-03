"""
Preprocess Node

清洗、去重、分段、语言检测
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class PreprocessConfig(NodeConfig):
    """Preprocess 节点配置"""
    
    min_content_length: int = 100
    max_content_length: int = 50000
    remove_duplicates: bool = True
    similarity_threshold: float = 0.85
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "min_content_length": 100,
            "max_content_length": 50000,
            "remove_duplicates": True,
            "similarity_threshold": 0.85
        }


class PreprocessNode(BaseNode):
    """预处理节点"""
    
    def __init__(self, config: PreprocessConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行预处理"""
        self.log(state, "开始预处理")
        
        try:
            cleaned = []
            
            for item in state.raw_contents:
                content = item.get("content", "")
                
                if len(content) < self.config.min_content_length:
                    continue
                
                if len(content) > self.config.max_content_length:
                    content = content[:self.config.max_content_length]
                
                cleaned_item = {
                    **item,
                    "content": self._clean_text(content),
                    "word_count": len(content.split())
                }
                
                cleaned.append(cleaned_item)
            
            if self.config.remove_duplicates:
                cleaned = self._remove_duplicates(cleaned)
            
            state.cleaned_contents = cleaned
            self.log(state, f"预处理完成，保留 {len(cleaned)} 条内容")
            
        except Exception as e:
            self.error(state, f"预处理失败: {str(e)}", detail=str(e))
        
        return state
    
    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        import re
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _remove_duplicates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重"""
        from simhash import Simhash
        
        seen_hashes = set()
        unique_items = []
        
        for item in items:
            content = item.get("content", "")
            hash_value = Simhash(content).value
            
            if hash_value not in seen_hashes:
                seen_hashes.add(hash_value)
                unique_items.append(item)
        
        return unique_items
