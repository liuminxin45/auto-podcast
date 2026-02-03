"""
Publish Node

生成RSS、预留发布接口
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class PublishConfig(NodeConfig):
    """Publish 节点配置"""
    
    rss_output_dir: str = "out/rss"
    podcast_title: str = "AI 播客"
    podcast_description: str = "AI 自动生成的播客节目"
    podcast_author: str = "Auto-Podcast"
    podcast_language: str = "zh-CN"
    podcast_category: str = "Technology"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "rss_output_dir": "out/rss",
            "podcast_title": "AI 播客",
            "podcast_description": "AI 自动生成的播客节目",
            "podcast_author": "Auto-Podcast",
            "podcast_language": "zh-CN",
            "podcast_category": "Technology"
        }


class PublishNode(BaseNode):
    """发布节点"""
    
    def __init__(self, config: PublishConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行发布"""
        self.log(state, "开始发布")
        
        try:
            rss_path = self._generate_rss(state)
            
            state.rss_path = rss_path
            state.publish_status = {
                "published": True,
                "rss_generated": True,
                "timestamp": datetime.now().isoformat()
            }
            
            self.log(state, f"发布完成: {rss_path}")
            
        except Exception as e:
            self.error(state, f"发布失败: {str(e)}", detail=str(e))
        
        return state
    
    def _generate_rss(self, state: PodcastState) -> str:
        """生成 RSS feed"""
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom
        
        output_dir = Path(self.config.rss_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        rss = Element('rss', version='2.0')
        rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
        
        channel = SubElement(rss, 'channel')
        
        SubElement(channel, 'title').text = self.config.podcast_title
        SubElement(channel, 'description').text = self.config.podcast_description
        SubElement(channel, 'language').text = self.config.podcast_language
        SubElement(channel, 'itunes:author').text = self.config.podcast_author
        SubElement(channel, 'itunes:category', text=self.config.podcast_category)
        
        storage_info = state.storage_info
        cover_url = storage_info.get("cover_url", "")
        if cover_url:
            image = SubElement(channel, 'itunes:image', href=cover_url)
        
        item = SubElement(channel, 'item')
        
        title = state.script.get("title", "未命名节目")
        description = state.script.get("description", "")
        
        SubElement(item, 'title').text = title
        SubElement(item, 'description').text = description
        SubElement(item, 'pubDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        audio_url = storage_info.get("audio_url", "")
        if audio_url:
            enclosure = SubElement(item, 'enclosure', url=audio_url, type='audio/mpeg')
            audio_size = state.audio_metadata.get("file_size_bytes", 0)
            enclosure.set('length', str(audio_size))
        
        duration = state.audio_metadata.get("duration_seconds", 0)
        SubElement(item, 'itunes:duration').text = str(int(duration))
        
        xml_str = minidom.parseString(tostring(rss)).toprettyxml(indent="  ")
        
        rss_file = output_dir / "feed.xml"
        with open(rss_file, "w", encoding="utf-8") as f:
            f.write(xml_str)
        
        return str(rss_file)
