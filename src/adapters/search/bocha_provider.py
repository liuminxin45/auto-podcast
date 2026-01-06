"""
Adapters Layer - Bocha Search Provider

博查搜索 API 的适配器实现。

TODO: 实现真实的博查 API 调用
- 从环境变量或配置读取 API Key
- 调用博查 API 端点
- 处理响应和错误
- 归一化结果格式

参考现有实现: src/research/sources/research_client.py 中的 bocha_web_search_items
"""

from __future__ import annotations

from typing import List, Dict, Any

from src.adapters.search.base import BaseSearchProvider
from src.domain.models import SearchError


class BochaSearchProvider(BaseSearchProvider):
    """博查搜索提供商（待实现）"""
    
    def __init__(self, api_key: str, timeout: int = 30):
        """
        Args:
            api_key: 博查 API Key
            timeout: 请求超时时间（秒）
        """
        super().__init__()
        self.api_key = api_key
        self.timeout = timeout
        
        if not api_key:
            raise ValueError("Bocha API Key 不能为空")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """执行博查搜索"""
        self._validate_query(query)
        
        # TODO: 实现真实的 API 调用
        # 1. 构建请求参数
        # 2. 调用 https://api.bocha.cn/v1/web-search
        # 3. 解析响应
        # 4. 归一化结果
        
        raise NotImplementedError(
            "博查搜索提供商尚未实现。"
            "请参考 src/research/sources/research_client.py 中的 bocha_web_search_items 实现。"
        )
    
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        return "bocha"
