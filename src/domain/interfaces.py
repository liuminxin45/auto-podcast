"""
Domain Layer - Abstract Interfaces

定义业务层的抽象接口，不依赖任何具体实现或框架。
这些接口可以被 adapters 层实现，被 services 层调用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class SearchProvider(ABC):
    """搜索服务提供商抽象接口"""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            **kwargs: 其他参数（如 freshness, language 等）
            
        Returns:
            搜索结果列表，每个结果包含 title, snippet, url 等字段
            
        Raises:
            SearchError: 搜索失败时抛出
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        pass


class Fetcher(ABC):
    """网页抓取器抽象接口"""
    
    @abstractmethod
    async def fetch(
        self,
        url: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        抓取网页内容
        
        Args:
            url: 目标 URL
            timeout: 超时时间（秒）
            
        Returns:
            包含 status_code, headers, content 等字段的字典
            
        Raises:
            FetchError: 抓取失败时抛出
        """
        pass


class Extractor(ABC):
    """内容提取器抽象接口"""
    
    @abstractmethod
    def extract(
        self,
        html: str,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从 HTML 中提取正文内容
        
        Args:
            html: HTML 内容
            url: 原始 URL（可选，用于解析相对路径）
            
        Returns:
            包含 title, content, author, publish_date 等字段的字典
            
        Raises:
            ExtractionError: 提取失败时抛出
        """
        pass
