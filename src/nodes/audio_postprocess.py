"""
Audio Postprocess Node

音频拼接、响度标准化、BGM混音、导出
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class AudioPostprocessConfig(NodeConfig):
    """AudioPostprocess 节点配置"""
    
    output_dir: str = "out/episodes"
    output_format: str = "mp3"
    normalize_loudness: bool = True
    target_loudness: float = -16.0
    add_bgm: bool = False
    bgm_volume: float = 0.1
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "output_dir": "out/episodes",
            "output_format": "mp3",
            "normalize_loudness": True,
            "target_loudness": -16.0,
            "add_bgm": False,
            "bgm_volume": 0.1
        }


class AudioPostprocessNode(BaseNode):
    """音频后处理节点"""
    
    def __init__(self, config: AudioPostprocessConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行音频后处理"""
        self.log(state, "开始音频后处理")
        
        try:
            segments = state.audio_segments
            
            if not segments:
                self.error(state, "没有可用的音频片段")
                return state
            
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            episode_id = state.episode_id or "episode"
            output_file = output_dir / f"{episode_id}.{self.config.output_format}"
            
            self._concatenate_audio(segments, str(output_file))
            
            if self.config.normalize_loudness:
                self._normalize_loudness(str(output_file))
            
            state.final_audio_path = str(output_file)
            state.audio_metadata = {
                "duration_seconds": self._get_duration(str(output_file)),
                "format": self.config.output_format,
                "file_size_bytes": output_file.stat().st_size
            }
            
            self.log(state, f"音频后处理完成: {output_file}")
            
        except Exception as e:
            self.error(state, f"音频后处理失败: {str(e)}", detail=str(e))
        
        return state
    
    def _concatenate_audio(self, segments: list, output_path: str) -> None:
        """拼接音频"""
        from pydub import AudioSegment
        
        combined = AudioSegment.empty()
        
        for segment_path in segments:
            if os.path.exists(segment_path):
                audio = AudioSegment.from_file(segment_path)
                combined += audio
        
        combined.export(output_path, format=self.config.output_format)
    
    def _normalize_loudness(self, audio_path: str) -> None:
        """响度标准化"""
        from pydub import AudioSegment
        import pyloudnorm as pyln
        import numpy as np
        
        audio = AudioSegment.from_file(audio_path)
        
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        samples = samples / (2**15)
        
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
        
        meter = pyln.Meter(audio.frame_rate)
        loudness = meter.integrated_loudness(samples)
        
        normalized = pyln.normalize.loudness(samples, loudness, self.config.target_loudness)
        
        normalized = (normalized * (2**15)).astype(np.int16)
        
        normalized_audio = AudioSegment(
            normalized.tobytes(),
            frame_rate=audio.frame_rate,
            sample_width=2,
            channels=audio.channels
        )
        
        normalized_audio.export(audio_path, format=self.config.output_format)
    
    def _get_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
