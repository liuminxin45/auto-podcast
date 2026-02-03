"""
LangGraph State Schema

定义主图的共享状态结构，所有节点通过此状态传递数据。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class PodcastState:
    """播客生成流程的共享状态"""
    
    # 全局标识与元数据
    episode_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # fetch 节点输出
    raw_contents: List[Dict[str, Any]] = field(default_factory=list)
    
    # preprocess 节点输出
    cleaned_contents: List[Dict[str, Any]] = field(default_factory=list)
    
    # research 节点输出
    researched_contents: List[Dict[str, Any]] = field(default_factory=list)
    
    # topic_selection 节点输出
    selected_topic: Dict[str, Any] = field(default_factory=dict)
    selected_materials: List[Dict[str, Any]] = field(default_factory=list)
    
    # script 节点输出
    script: Dict[str, Any] = field(default_factory=dict)
    
    # stages 节点输出
    stages: List[Dict[str, Any]] = field(default_factory=list)
    
    # tts 节点输出
    audio_segments: List[str] = field(default_factory=list)
    
    # audio_postprocess 节点输出
    final_audio_path: str = ""
    audio_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # assets 节点输出
    cover_path: str = ""
    intro_outro_paths: Dict[str, str] = field(default_factory=dict)
    
    # store 节点输出
    storage_info: Dict[str, Any] = field(default_factory=dict)
    
    # publish 节点输出
    rss_path: str = ""
    publish_status: Dict[str, Any] = field(default_factory=dict)
    
    # subtitles 节点输出（占位，默认不使用）
    subtitle_path: str = ""
    
    # 运行时配置覆盖（可选）
    runtime_config: Dict[str, Any] = field(default_factory=dict)
    
    # 错误与日志
    errors: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
