"""
Domain Layer - Domain Models

定义领域模型，纯数据结构，不包含业务逻辑。
使用 dataclass 保持简洁，避免过度设计。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    snippet: str
    url: str
    source: Optional[str] = None
    published_date: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "source": self.source,
            "published_date": self.published_date,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class FetchResult:
    """抓取结果"""
    url: str
    title: Optional[str] = None
    content: str = ""
    author: Optional[str] = None
    publish_date: Optional[str] = None
    status_code: int = 200
    content_length: int = 0
    is_truncated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "publish_date": self.publish_date,
            "status_code": self.status_code,
            "content_length": self.content_length,
            "is_truncated": self.is_truncated,
            "metadata": self.metadata,
        }


@dataclass
class ErrorDetail:
    """错误详情"""
    code: str
    message: str
    detail: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result


@dataclass
class OperationResult:
    """操作结果（统一返回结构）"""
    ok: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result: Dict[str, Any] = {"ok": self.ok}
        
        if self.ok and self.data is not None:
            result["data"] = self.data
        
        if not self.ok and self.error is not None:
            result["error"] = self.error.to_dict()
        
        if self.meta:
            result["meta"] = self.meta
        
        return result
    
    @classmethod
    def success(cls, data: Any, meta: Optional[Dict[str, Any]] = None) -> OperationResult:
        """创建成功结果"""
        return cls(ok=True, data=data, meta=meta or {})
    
    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        detail: Optional[Any] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """创建失败结果"""
        error = ErrorDetail(code=code, message=message, detail=detail)
        return cls(ok=False, error=error, meta=meta or {})


# 自定义异常
class DomainError(Exception):
    """领域层基础异常"""
    def __init__(self, code: str, message: str, detail: Optional[Any] = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class SearchError(DomainError):
    """搜索错误"""
    pass


class FetchError(DomainError):
    """抓取错误"""
    pass


class ExtractionError(DomainError):
    """提取错误"""
    pass


class ValidationError(DomainError):
    """参数校验错误"""
    pass
