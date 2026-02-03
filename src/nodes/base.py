"""
Base Node Configuration

所有节点的基类，定义配置规范与节点接口。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any
from ..schemas.state import PodcastState


@dataclass
class NodeConfig(ABC):
    """节点配置基类"""
    
    @classmethod
    @abstractmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """返回默认配置"""
        pass
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        """从字典创建配置实例"""
        defaults = cls.get_defaults()
        merged = {**defaults, **config}
        return cls(**merged)


class BaseNode(ABC):
    """节点基类"""
    
    def __init__(self, config: NodeConfig):
        self.config = config
    
    @abstractmethod
    def __call__(self, state: PodcastState) -> PodcastState:
        """执行节点逻辑，返回更新后的状态"""
        pass
    
    def log(self, state: PodcastState, message: str) -> None:
        """添加日志到状态"""
        state.logs.append(f"[{self.__class__.__name__}] {message}")
    
    def error(self, state: PodcastState, error_msg: str, detail: Any = None) -> None:
        """添加错误到状态"""
        state.errors.append({
            "node": self.__class__.__name__,
            "message": error_msg,
            "detail": detail
        })
