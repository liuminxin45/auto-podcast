"""
Adapters Layer - HTTP Fetcher

使用 httpx 抓取网页内容。
"""

from __future__ import annotations

import logging
from typing import Dict, Any

import httpx

from src.domain.interfaces import Fetcher
from src.domain.models import FetchError


class HttpFetcher(Fetcher):
    """HTTP 抓取器"""
    
    def __init__(
        self,
        timeout: int = 30,
        max_redirects: int = 5,
        user_agent: str | None = None,
        logger: logging.Logger | None = None
    ):
        """
        Args:
            timeout: 请求超时时间（秒）
            max_redirects: 最大重定向次数
            user_agent: User-Agent 字符串
            logger: 日志记录器
        """
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    async def fetch(
        self,
        url: str,
        timeout: int | None = None
    ) -> Dict[str, Any]:
        """抓取网页内容"""
        if not url or not url.startswith(("http://", "https://")):
            raise FetchError("INVALID_URL", f"无效的 URL: {url}")
        
        timeout_val = timeout or self.timeout
        
        self.logger.info(f"抓取 URL: {url}")
        
        try:
            async with httpx.AsyncClient(
                timeout=timeout_val,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers={"User-Agent": self.user_agent}
            ) as client:
                response = await client.get(url)
                
                # 检查状态码
                if response.status_code >= 400:
                    raise FetchError(
                        "HTTP_ERROR",
                        f"HTTP {response.status_code}",
                        detail={"url": url, "status_code": response.status_code}
                    )
                
                # 检查内容类型
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type.lower():
                    self.logger.warning(f"非 HTML 内容: {content_type}")
                
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "content": response.text,
                    "url": str(response.url),  # 可能经过重定向
                    "encoding": response.encoding,
                }
        
        except httpx.TimeoutException:
            raise FetchError(
                "TIMEOUT",
                f"请求超时（{timeout_val}秒）",
                detail={"url": url, "timeout": timeout_val}
            )
        except httpx.HTTPError as e:
            raise FetchError(
                "NETWORK_ERROR",
                f"网络错误: {str(e)}",
                detail={"url": url, "error": str(e)}
            )
        except Exception as e:
            raise FetchError(
                "UNKNOWN_ERROR",
                f"未知错误: {str(e)}",
                detail={"url": url, "error": str(e)}
            )
