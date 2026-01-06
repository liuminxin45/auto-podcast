"""
Adapters Layer - Search Provider Base

SearchProvider 的基础实现，提供通用功能。
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

from src.domain.interfaces import SearchProvider
from src.domain.models import SearchError


class BaseSearchProvider(SearchProvider):
    """SearchProvider 基类，提供通用功能"""
    
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    def _normalize_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        归一化搜索结果格式
        
        不同的搜索 API 返回格式不同，这里统一转换为标准格式：
        {
            "title": str,
            "snippet": str,
            "url": str,
            "source": str (optional),
            "published_date": str (optional),
            "score": float (optional)
        }
        """
        return {
            "title": raw_result.get("title", ""),
            "snippet": raw_result.get("snippet", raw_result.get("description", "")),
            "url": raw_result.get("url", ""),
            "source": raw_result.get("source"),
            "published_date": raw_result.get("published_date"),
            "score": raw_result.get("score"),
        }
    
    def _validate_query(self, query: str) -> None:
        """校验查询参数"""
        if not query or not query.strip():
            raise SearchError("INVALID_QUERY", "查询不能为空")
        
        if len(query) > 500:
            raise SearchError("QUERY_TOO_LONG", f"查询过长（{len(query)} 字符），最大 500 字符")
