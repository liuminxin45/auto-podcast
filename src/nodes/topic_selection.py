"""
Topic Selection Node

选题、聚类、排序
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any, List
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class TopicSelectionConfig(NodeConfig):
    """TopicSelection 节点配置"""
    
    min_cluster_size: int = 3
    max_topics: int = 1
    use_llm_scoring: bool = True
    llm_model: str = "gpt-4o-mini"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "min_cluster_size": 3,
            "max_topics": 1,
            "use_llm_scoring": True,
            "llm_model": "gpt-4o-mini"
        }


class TopicSelectionNode(BaseNode):
    """选题节点"""
    
    def __init__(self, config: TopicSelectionConfig):
        super().__init__(config)
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行选题"""
        self.log(state, "开始选题")
        
        try:
            contents = state.researched_contents
            
            if not contents:
                self.error(state, "没有可用内容进行选题")
                return state
            
            clusters = self._cluster_contents(contents)
            
            best_cluster = max(clusters, key=lambda c: len(c["items"]))
            
            state.selected_topic = {
                "title": best_cluster.get("title", "未命名主题"),
                "description": best_cluster.get("description", ""),
                "keywords": best_cluster.get("keywords", [])
            }
            
            state.selected_materials = best_cluster.get("items", [])
            
            self.log(state, f"选题完成: {state.selected_topic['title']}")
            
        except Exception as e:
            self.error(state, f"选题失败: {str(e)}", detail=str(e))
        
        return state
    
    def _cluster_contents(self, contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """聚类内容"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        import numpy as np
        
        if len(contents) < self.config.min_cluster_size:
            return [{
                "title": "综合话题",
                "description": "",
                "keywords": [],
                "items": contents
            }]
        
        texts = [item.get("content", "") for item in contents]
        
        vectorizer = TfidfVectorizer(max_features=100)
        X = vectorizer.fit_transform(texts)
        
        n_clusters = min(3, len(contents) // self.config.min_cluster_size)
        if n_clusters < 1:
            n_clusters = 1
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(X)
        
        clusters = []
        for i in range(n_clusters):
            cluster_items = [contents[j] for j in range(len(contents)) if labels[j] == i]
            
            if cluster_items:
                clusters.append({
                    "title": f"话题 {i+1}",
                    "description": "",
                    "keywords": [],
                    "items": cluster_items
                })
        
        return clusters
