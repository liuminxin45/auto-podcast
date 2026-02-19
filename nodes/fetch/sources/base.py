"""
Base class for fetch data sources.
All custom data sources should inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class FetchSourceBase(ABC):
    """Base class for all fetch data sources."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of this data source."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this source fetches."""
        pass
    
    @abstractmethod
    def fetch(self, fetch_logs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from this source.
        
        Returns:
            List of items in standard format:
            [
                {
                    "title": str,        # 标题
                    "content": str,      # 内容
                    "url": str,          # 链接（可选）
                    "published": str,    # 发布时间（可选）
                    "source": str,       # 来源标识
                    "type": str,         # 类型标识
                },
                ...
            ]
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about this source."""
        return {
            "name": self.name,
            "description": self.description,
        }
