"""
Fetch Node

抓取原始素材（RSS订阅、网页、API等）
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class FetchConfig(NodeConfig):
    """Fetch 节点配置"""
    
    sources: List[Dict[str, str]] = field(default_factory=list)
    max_items_per_source: int = 10
    timeout: int = 30
    user_agent: str = "AutoPodcast/1.0"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "sources": [],
            "max_items_per_source": 10,
            "timeout": 30,
            "user_agent": "AutoPodcast/1.0"
        }


class FetchNode(BaseNode):
    """抓取节点"""
    
    def __init__(self, config: FetchConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行抓取"""
        self.log(state, "开始抓取素材")
        
        try:
            raw_contents = []
            
            for source in self.config.sources:
                source_type = source.get("type", "rss")
                source_url = source.get("url", "")
                
                if not source_url:
                    continue
                
                if source_type == "rss":
                    items = self._fetch_rss(source_url)
                elif source_type == "web":
                    items = self._fetch_web(source_url)
                else:
                    self.log(state, f"未知的源类型: {source_type}")
                    continue
                
                raw_contents.extend(items[:self.config.max_items_per_source])
            
            state.raw_contents = raw_contents
            self.log(state, f"抓取完成，共 {len(raw_contents)} 条内容")
            
        except Exception as e:
            self.error(state, f"抓取失败: {str(e)}", detail=str(e))
        
        return state
    
    def _fetch_rss(self, url: str) -> List[Dict[str, Any]]:
        """抓取 RSS 订阅"""
        import feedparser
        
        feed = feedparser.parse(url)
        items = []
        
        for entry in feed.entries:
            items.append({
                "title": entry.get("title", ""),
                "content": entry.get("summary", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": url,
                "type": "rss"
            })
        
        return items
    
    def _fetch_web(self, url: str) -> List[Dict[str, Any]]:
        """抓取网页内容"""
        import requests
        from trafilatura import extract
        
        response = requests.get(url, timeout=self.config.timeout, headers={
            "User-Agent": self.config.user_agent
        })
        
        content = extract(response.text)
        
        return [{
            "title": "",
            "content": content or "",
            "url": url,
            "published": "",
            "source": url,
            "type": "web"
        }]
