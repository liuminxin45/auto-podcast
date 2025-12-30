"""
Segment Data Models

数据模型：SegmentScript, SegmentAudio, EpisodeManifest
用于分段播客生成流程
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class SegmentScript:
    """单个段落的脚本"""
    id: str  # S0, S1, S2, S3, S4, S5
    type: str  # OPENING, OVERVIEW, HISTORY, DETAIL_NEWS, DEEP_DIVE, CLOSING
    title: str
    text: str  # 可口播文本
    duration_sec: int  # 预估时长（秒）
    facts_used: List[str] = field(default_factory=list)  # 使用的新闻ID
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "text": self.text,
            "duration_sec": self.duration_sec,
            "facts_used": self.facts_used,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> SegmentScript:
        return cls(
            id=data["id"],
            type=data["type"],
            title=data.get("title", ""),
            text=data["text"],
            duration_sec=data.get("duration_sec", 0),
            facts_used=data.get("facts_used", []),
        )


@dataclass
class SegmentAudio:
    """单个段落的音频"""
    segment_id: str
    mp3_path: str
    duration_ms: int  # 实际音频时长（毫秒）
    gen_ms: int  # 生成耗时（毫秒）
    tts_ms: int  # TTS耗时（毫秒）
    cached: bool = False  # 是否使用缓存
    
    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "mp3_path": self.mp3_path,
            "duration_ms": self.duration_ms,
            "gen_ms": self.gen_ms,
            "tts_ms": self.tts_ms,
            "cached": self.cached,
        }


@dataclass
class BGMInsert:
    """BGM插入点"""
    name: str  # transition / outro
    path: str
    insert_after: str  # 在哪个segment之后插入
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "insert_after": self.insert_after,
        }


@dataclass
class EpisodeManifest:
    """Episode清单"""
    episode_id: str
    segments: List[SegmentAudio]
    bgm: List[BGMInsert]
    final_path: str
    created_at: str
    total_duration_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "segments": [s.to_dict() for s in self.segments],
            "bgm": [b.to_dict() for b in self.bgm],
            "final_path": self.final_path,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms,
        }
    
    def save(self, path: str) -> None:
        """保存到JSON文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: str) -> EpisodeManifest:
        """从JSON文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            episode_id=data["episode_id"],
            segments=[SegmentAudio(**s) for s in data["segments"]],
            bgm=[BGMInsert(**b) for b in data["bgm"]],
            final_path=data["final_path"],
            created_at=data["created_at"],
            total_duration_ms=data.get("total_duration_ms", 0),
        )


# 段落类型定义
SEGMENT_TYPES = {
    "S0": "OPENING",
    "S1": "OVERVIEW",
    "S2": "HISTORY",
    "S3": "DETAIL_NEWS",
    "S4": "DEEP_DIVE",
    "S5": "CLOSING",
}

# 段落顺序
SEGMENT_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
