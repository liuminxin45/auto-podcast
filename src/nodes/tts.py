"""
TTS Node

文本转语音
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List
from pathlib import Path
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class TTSConfig(NodeConfig):
    """TTS 节点配置"""
    
    engine: str = "edge-tts"
    voice_mapping: Dict[str, str] = field(default_factory=dict)
    default_voice: str = "zh-CN-XiaoxiaoNeural"
    output_dir: str = "out/audio_segments"
    rate: str = "+0%"
    volume: str = "+0%"
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "engine": "edge-tts",
            "voice_mapping": {
                "主持人A": "zh-CN-XiaoxiaoNeural",
                "主持人B": "zh-CN-YunxiNeural"
            },
            "default_voice": "zh-CN-XiaoxiaoNeural",
            "output_dir": "out/audio_segments",
            "rate": "+0%",
            "volume": "+0%"
        }


class TTSNode(BaseNode):
    """TTS 节点"""
    
    def __init__(self, config: TTSConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行 TTS"""
        self.log(state, "开始 TTS 转换")
        
        try:
            stages = state.stages
            
            if not stages:
                self.error(state, "没有可用的分段内容")
                return state
            
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            audio_segments = []
            
            for stage in stages:
                order = stage.get("order", 0)
                speaker = stage.get("speaker", "")
                text = stage.get("text", "")
                
                voice = self.config.voice_mapping.get(speaker, self.config.default_voice)
                
                output_file = output_dir / f"segment_{order:03d}.mp3"
                
                self._synthesize(text, voice, str(output_file))
                
                audio_segments.append(str(output_file))
            
            state.audio_segments = audio_segments
            self.log(state, f"TTS 完成，生成 {len(audio_segments)} 个音频片段")
            
        except Exception as e:
            self.error(state, f"TTS 失败: {str(e)}", detail=str(e))
        
        return state
    
    def _synthesize(self, text: str, voice: str, output_path: str) -> None:
        """合成语音"""
        import asyncio
        import edge_tts
        
        async def _async_synthesize():
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.config.rate,
                volume=self.config.volume
            )
            await communicate.save(output_path)
        
        asyncio.run(_async_synthesize())
