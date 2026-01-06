"""
Adapters Layer - Mock Search Provider

用于开发和测试的 Mock 搜索提供商。
返回预设的假数据，不依赖外部 API。
"""

from __future__ import annotations

import asyncio
from typing import List, Dict, Any

from src.adapters.search.base import BaseSearchProvider


class MockSearchProvider(BaseSearchProvider):
    """Mock 搜索提供商（用于开发和测试）"""
    
    def __init__(self, delay: float = 0.1):
        """
        Args:
            delay: 模拟网络延迟（秒）
        """
        super().__init__()
        self.delay = delay
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """执行 Mock 搜索"""
        self._validate_query(query)
        
        self.logger.info(f"Mock 搜索: query='{query}', max_results={max_results}")
        
        # 模拟网络延迟
        await asyncio.sleep(self.delay)
        
        # 返回假数据
        results = []
        for i in range(min(max_results, 5)):
            results.append({
                "title": f"Mock 搜索结果 {i+1}: {query}",
                "snippet": f"这是关于 '{query}' 的第 {i+1} 条模拟搜索结果。包含相关信息和摘要内容。",
                "url": f"https://example.com/result/{i+1}",
                "source": "Mock Provider",
                "published_date": "2026-01-06",
                "score": 0.9 - i * 0.1,
            })
        
        return [self._normalize_result(r) for r in results]
    
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        return "mock"
