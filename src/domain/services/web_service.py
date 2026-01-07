"""
Domain Services Layer - Web Service

纯业务逻辑：搜索和抓取的组合、裁剪、去噪。
不依赖任何框架，只依赖 domain 层的接口和模型。
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from src.domain.interfaces import SearchProvider, Fetcher, Extractor
from src.domain.models import (
    SearchResult,
    FetchResult,
    SearchError,
    FetchError,
    ExtractionError,
    ValidationError,
)


class WebService:
    """Web 服务：搜索和抓取的业务逻辑"""
    
    def __init__(
        self,
        search_provider: SearchProvider,
        fetcher: Fetcher,
        extractor: Extractor,
        max_content_length: int = 20000,
        logger: logging.Logger | None = None
    ):
        """
        Args:
            search_provider: 搜索提供商
            fetcher: 抓取器
            extractor: 内容提取器
            max_content_length: 最大内容长度（字符数）
            logger: 日志记录器
        """
        self.search_provider = search_provider
        self.fetcher = fetcher
        self.extractor = extractor
        self.max_content_length = max_content_length
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            **kwargs: 其他参数
            
        Returns:
            搜索结果列表
            
        Raises:
            ValidationError: 参数校验失败
            SearchError: 搜索失败
        """
        # 参数校验
        self.logger.debug(f"[WebService] 接收搜索请求: query='{query[:100]}', max_results={max_results}, kwargs={kwargs}")
        
        if not query or not query.strip():
            self.logger.error(f"[WebService] ✗ 参数校验失败: 查询为空")
            raise ValidationError("EMPTY_QUERY", "搜索查询不能为空")
        
        if max_results < 1 or max_results > 50:
            self.logger.error(f"[WebService] ✗ 参数校验失败: max_results={max_results} 超出范围")
            raise ValidationError("INVALID_MAX_RESULTS", "max_results 必须在 1-50 之间")
        
        self.logger.info(
            f"[WebService] 开始搜索: query='{query[:50]}...', max_results={max_results}, "
            f"provider={self.search_provider.get_provider_name()}"
        )
        
        try:
            # 调用搜索提供商
            self.logger.debug(f"[WebService] 调用搜索提供商: {self.search_provider.get_provider_name()}")
            raw_results = await self.search_provider.search(
                query=query,
                max_results=max_results,
                **kwargs
            )
            
            self.logger.info(f"[WebService] 搜索提供商返回 {len(raw_results)} 条原始结果")
            
            # 转换为领域模型
            results = []
            self.logger.debug(f"[WebService] 开始转换为领域模型...")
            for idx, raw in enumerate(raw_results):
                result = SearchResult(
                    title=raw.get("title", ""),
                    snippet=raw.get("snippet", ""),
                    url=raw.get("url", ""),
                    source=raw.get("source"),
                    published_date=raw.get("published_date"),
                    score=raw.get("score"),
                    metadata=raw.get("metadata", {}),
                )
                results.append(result)
                
                if idx == 0:
                    self.logger.debug(f"[WebService] 首条结果: title='{result.title[:50]}', url={result.url}")
            
            self.logger.info(f"[WebService] ✓ 搜索完成: 返回 {len(results)} 条结果")
            return results
        
        except SearchError as e:
            self.logger.error(f"[WebService] ✗ 搜索错误: {e.message}")
            raise
        except Exception as e:
            self.logger.error(f"[WebService] ✗ 搜索失败: {e}", exc_info=True)
            raise SearchError("SEARCH_FAILED", f"搜索失败: {str(e)}", detail=str(e))
    
    async def fetch(
        self,
        url: str,
        extract_content: bool = True,
        timeout: int | None = None
    ) -> FetchResult:
        """
        抓取网页内容
        
        Args:
            url: 目标 URL
            extract_content: 是否提取正文（否则只返回原始 HTML）
            timeout: 超时时间（秒）
            
        Returns:
            抓取结果
            
        Raises:
            ValidationError: 参数校验失败
            FetchError: 抓取失败
            ExtractionError: 内容提取失败
        """
        # 参数校验
        self.logger.debug(f"[WebService] 接收抓取请求: url={url}, extract={extract_content}, timeout={timeout}")
        
        if not url or not url.strip():
            self.logger.error(f"[WebService] ✗ 参数校验失败: URL 为空")
            raise ValidationError("EMPTY_URL", "URL 不能为空")
        
        if not url.startswith(("http://", "https://")):
            self.logger.error(f"[WebService] ✗ 参数校验失败: URL 格式错误 {url}")
            raise ValidationError("INVALID_URL", "URL 必须以 http:// 或 https:// 开头")
        
        self.logger.info(f"[WebService] 开始抓取: url={url}, extract={extract_content}")
        
        try:
            # 抓取 HTML
            self.logger.debug(f"[WebService] 调用 Fetcher 抓取 HTML...")
            fetch_response = await self.fetcher.fetch(url, timeout=timeout or 30)
            html = fetch_response.get("content", "")
            status_code = fetch_response.get("status_code", 200)
            
            self.logger.info(f"[WebService] HTML 抓取完成: status={status_code}, length={len(html)}")
            
            if not extract_content:
                # 不提取正文，直接返回 HTML
                self.logger.info(f"[WebService] ✓ 返回原始 HTML: length={len(html)}")
                return FetchResult(
                    url=url,
                    content=html,
                    status_code=status_code,
                    content_length=len(html),
                    metadata={"raw_html": True},
                )
            
            # 提取正文
            self.logger.debug(f"[WebService] 调用 Extractor 提取正文...")
            extracted = self.extractor.extract(html, url=url)
            
            title = extracted.get("title")
            content = extracted.get("content", "")
            author = extracted.get("author")
            publish_date = extracted.get("publish_date")
            
            self.logger.info(f"[WebService] 正文提取完成: title='{title}', content_length={len(content)}")
            
            # 裁剪内容
            is_truncated = False
            original_length = len(content)
            if original_length > self.max_content_length:
                content = content[:self.max_content_length]
                is_truncated = True
                self.logger.info(f"[WebService] 内容被裁剪: {original_length} -> {self.max_content_length}")
            
            result = FetchResult(
                url=url,
                title=title,
                content=content,
                author=author,
                publish_date=publish_date,
                status_code=status_code,
                content_length=len(content),
                is_truncated=is_truncated,
                metadata={
                    "original_length": len(extracted.get("content", "")),
                    "max_length": self.max_content_length,
                },
            )
            
            self.logger.info(
                f"[WebService] ✓ 抓取完成: title='{title}', content_length={len(content)}, "
                f"truncated={is_truncated}"
            )
            
            return result
        
        except (FetchError, ExtractionError) as e:
            self.logger.error(f"[WebService] ✗ 抓取/提取错误: {e.message if hasattr(e, 'message') else str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"[WebService] ✗ 抓取失败: {e}", exc_info=True)
            raise FetchError("FETCH_FAILED", f"抓取失败: {str(e)}", detail=str(e))
