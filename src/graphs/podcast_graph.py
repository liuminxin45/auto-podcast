"""
Podcast Generation Graph

LangGraph 主图定义，连接所有节点形成完整流程。
"""

from __future__ import annotations
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from ..schemas.state import PodcastState
from ..nodes import (
    FetchNode, FetchConfig,
    PreprocessNode, PreprocessConfig,
    ResearchNode, ResearchConfig,
    TopicSelectionNode, TopicSelectionConfig,
    ScriptNode, ScriptConfig,
    StagesNode, StagesConfig,
    TTSNode, TTSConfig,
    AudioPostprocessNode, AudioPostprocessConfig,
    AssetsNode, AssetsConfig,
    StoreNode, StoreConfig,
    PublishNode, PublishConfig,
    SubtitlesNode, SubtitlesConfig,
)


def create_podcast_graph(config: Dict[str, Any] = None) -> CompiledStateGraph:
    """创建播客生成主图
    
    Args:
        config: 节点配置字典，可选
        
    Returns:
        编译后的 LangGraph 状态图
    """
    
    config = config or {}
    
    fetch_node = FetchNode(FetchConfig.from_dict(config.get("fetch", {})))
    preprocess_node = PreprocessNode(PreprocessConfig.from_dict(config.get("preprocess", {})))
    research_node = ResearchNode(ResearchConfig.from_dict(config.get("research", {})))
    topic_selection_node = TopicSelectionNode(TopicSelectionConfig.from_dict(config.get("topic_selection", {})))
    script_node = ScriptNode(ScriptConfig.from_dict(config.get("script", {})))
    stages_node = StagesNode(StagesConfig.from_dict(config.get("stages", {})))
    tts_node = TTSNode(TTSConfig.from_dict(config.get("tts", {})))
    audio_postprocess_node = AudioPostprocessNode(AudioPostprocessConfig.from_dict(config.get("audio_postprocess", {})))
    assets_node = AssetsNode(AssetsConfig.from_dict(config.get("assets", {})))
    store_node = StoreNode(StoreConfig.from_dict(config.get("store", {})))
    publish_node = PublishNode(PublishConfig.from_dict(config.get("publish", {})))
    subtitles_node = SubtitlesNode(SubtitlesConfig.from_dict(config.get("subtitles", {})))
    
    graph = StateGraph(PodcastState)
    
    graph.add_node("fetch", fetch_node)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("research", research_node)
    graph.add_node("topic_selection", topic_selection_node)
    graph.add_node("script", script_node)
    graph.add_node("stages", stages_node)
    graph.add_node("tts", tts_node)
    graph.add_node("audio_postprocess", audio_postprocess_node)
    graph.add_node("assets", assets_node)
    graph.add_node("store", store_node)
    graph.add_node("publish", publish_node)
    graph.add_node("subtitles", subtitles_node)
    
    graph.set_entry_point("fetch")
    
    graph.add_edge("fetch", "preprocess")
    graph.add_edge("preprocess", "research")
    graph.add_edge("research", "topic_selection")
    graph.add_edge("topic_selection", "script")
    graph.add_edge("script", "stages")
    graph.add_edge("stages", "tts")
    graph.add_edge("tts", "audio_postprocess")
    graph.add_edge("audio_postprocess", "assets")
    graph.add_edge("assets", "store")
    graph.add_edge("store", "publish")
    graph.add_edge("publish", END)
    
    return graph.compile()
