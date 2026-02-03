"""
Assets Node

生成封面、片头片尾素材
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class AssetsConfig(NodeConfig):
    """Assets 节点配置"""
    
    output_dir: str = "out/assets"
    generate_cover: bool = True
    cover_size: tuple = (1400, 1400)
    default_cover_path: str = ""
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "output_dir": "out/assets",
            "generate_cover": True,
            "cover_size": (1400, 1400),
            "default_cover_path": ""
        }


class AssetsNode(BaseNode):
    """素材生成节点"""
    
    def __init__(self, config: AssetsConfig):
        super().__init__(config)
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """生成素材"""
        self.log(state, "开始生成素材")
        
        try:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            episode_id = state.episode_id or "episode"
            
            if self.config.generate_cover:
                cover_path = self._generate_cover(state, output_dir, episode_id)
                state.cover_path = cover_path
            elif self.config.default_cover_path and os.path.exists(self.config.default_cover_path):
                state.cover_path = self.config.default_cover_path
            
            self.log(state, f"素材生成完成")
            
        except Exception as e:
            self.error(state, f"素材生成失败: {str(e)}", detail=str(e))
        
        return state
    
    def _generate_cover(self, state: PodcastState, output_dir: Path, episode_id: str) -> str:
        """生成封面（简单实现）"""
        from PIL import Image, ImageDraw, ImageFont
        
        width, height = self.config.cover_size
        
        img = Image.new('RGB', (width, height), color=(73, 109, 137))
        
        draw = ImageDraw.Draw(img)
        
        title = state.script.get("title", "播客节目")
        
        try:
            font = ImageFont.truetype("arial.ttf", 80)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), title, fill=(255, 255, 255), font=font)
        
        cover_path = output_dir / f"{episode_id}_cover.png"
        img.save(cover_path)
        
        return str(cover_path)
