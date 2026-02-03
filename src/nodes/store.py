"""
Store Node

本地存储、预留云存储接口
"""

from __future__ import annotations
import os
import shutil
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class StoreConfig(NodeConfig):
    """Store 节点配置"""
    
    storage_type: str = "local"
    local_base_dir: str = "out/published"
    generate_metadata: bool = True
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "storage_type": "local",
            "local_base_dir": "out/published",
            "generate_metadata": True
        }


class StoreNode(BaseNode):
    """存储节点"""
    
    def __init__(self, config: StoreConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行存储"""
        self.log(state, "开始存储")
        
        try:
            if self.config.storage_type == "local":
                storage_info = self._store_local(state)
            else:
                self.error(state, f"不支持的存储类型: {self.config.storage_type}")
                return state
            
            state.storage_info = storage_info
            self.log(state, f"存储完成: {storage_info.get('base_dir', '')}")
            
        except Exception as e:
            self.error(state, f"存储失败: {str(e)}", detail=str(e))
        
        return state
    
    def _store_local(self, state: PodcastState) -> Dict[str, Any]:
        """本地存储"""
        episode_id = state.episode_id or "episode"
        
        base_dir = Path(self.config.local_base_dir) / episode_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = state.final_audio_path
        cover_path = state.cover_path
        
        stored_audio = ""
        stored_cover = ""
        
        if audio_path and os.path.exists(audio_path):
            dest_audio = base_dir / Path(audio_path).name
            shutil.copy2(audio_path, dest_audio)
            stored_audio = str(dest_audio)
        
        if cover_path and os.path.exists(cover_path):
            dest_cover = base_dir / Path(cover_path).name
            shutil.copy2(cover_path, dest_cover)
            stored_cover = str(dest_cover)
        
        if self.config.generate_metadata:
            import json
            metadata = {
                "episode_id": episode_id,
                "title": state.script.get("title", ""),
                "description": state.script.get("description", ""),
                "audio_path": stored_audio,
                "cover_path": stored_cover,
                "duration_seconds": state.audio_metadata.get("duration_seconds", 0),
                "created_at": state.created_at
            }
            
            metadata_path = base_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "storage_type": "local",
            "base_dir": str(base_dir),
            "audio_path": stored_audio,
            "cover_path": stored_cover,
            "audio_url": f"file://{stored_audio}",
            "cover_url": f"file://{stored_cover}"
        }
