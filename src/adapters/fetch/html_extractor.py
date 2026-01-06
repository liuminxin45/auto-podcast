"""
Adapters Layer - HTML Extractor

从 HTML 中提取正文内容。
使用 BeautifulSoup 和简单的启发式规则。
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup

from src.domain.interfaces import Extractor
from src.domain.models import ExtractionError


class HtmlExtractor(Extractor):
    """HTML 内容提取器"""
    
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    def extract(
        self,
        html: str,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 HTML 中提取正文内容"""
        if not html or not html.strip():
            raise ExtractionError("EMPTY_HTML", "HTML 内容为空")
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 提取标题
            title = self._extract_title(soup)
            
            # 提取正文
            content = self._extract_content(soup)
            
            # 提取元数据
            author = self._extract_meta(soup, ["author", "article:author"])
            publish_date = self._extract_meta(soup, [
                "article:published_time",
                "datePublished",
                "publish_date"
            ])
            
            return {
                "title": title,
                "content": content,
                "author": author,
                "publish_date": publish_date,
                "url": url,
            }
        
        except Exception as e:
            raise ExtractionError(
                "PARSE_ERROR",
                f"解析 HTML 失败: {str(e)}",
                detail={"error": str(e)}
            )
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """提取标题"""
        # 优先级：h1 > og:title > title
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]
        
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取正文内容"""
        # 移除不需要的标签
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # 尝试找到主要内容区域
        main_content = None
        
        # 常见的正文容器
        for selector in ["article", "main", ".content", ".article", "#content"]:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # 如果没找到，使用 body
        if not main_content:
            main_content = soup.find("body")
        
        if not main_content:
            return ""
        
        # 提取文本
        text = main_content.get_text(separator="\n", strip=True)
        
        # 清理多余的空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
    
    def _extract_meta(self, soup: BeautifulSoup, names: list[str]) -> Optional[str]:
        """提取 meta 标签内容"""
        for name in names:
            # 尝试 property
            meta = soup.find("meta", property=name)
            if meta and meta.get("content"):
                return meta["content"]
            
            # 尝试 name
            meta = soup.find("meta", attrs={"name": name})
            if meta and meta.get("content"):
                return meta["content"]
        
        return None
