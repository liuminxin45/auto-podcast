"""
Adapters Layer - Unified Research Provider

使用项目现有的 UnifiedResearchClient 作为搜索提供商。
这样可以复用已有的博查、Anspire、MetaSo 等搜索实现。
"""

from __future__ import annotations

import asyncio
from typing import List, Dict, Any

from src.adapters.search.base import BaseSearchProvider
from src.research.sources.research_client import create_client_from_env
from src.domain.models import SearchError


class UnifiedResearchProvider(BaseSearchProvider):
    """统一研究客户端搜索提供商"""
    
    def __init__(self, provider: str = "bocha"):
        """
        Args:
            provider: 研究服务提供商 (metaso, anspire, bocha)
        """
        super().__init__()
        self.provider_name = provider
        
        # 创建研究客户端
        try:
            self.client = create_client_from_env(provider=provider)
            self.logger.info(f"初始化 {provider} 研究客户端成功")
        except Exception as e:
            self.logger.error(f"初始化 {provider} 研究客户端失败: {e}")
            raise SearchError(
                "INIT_ERROR",
                f"无法初始化 {provider} 研究客户端: {str(e)}",
                detail=str(e)
            )
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """执行搜索"""
        self._validate_query(query)
        
        self.logger.info(f"使用 {self.provider_name} 搜索: query='{query[:50]}...', max_results={max_results}")
        
        # 构建搜索条目
        items = [{
            "id": "search_query",
            "title": query,
            "summary": "",
        }]
        
        try:
            # 在线程池中执行同步调用（因为 research_items 不是 async）
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: self.client.research_items(items, max_items=1)
            )
            
            if not output.success:
                raise SearchError(
                    "SEARCH_FAILED",
                    f"搜索失败: {output.error}",
                    detail=output.error
                )
            
            # 解析结果
            results = self._parse_research_output(output, max_results)
            
            self.logger.info(f"搜索完成: 返回 {len(results)} 条结果")
            return results
        
        except SearchError:
            raise
        except Exception as e:
            self.logger.error(f"搜索异常: {e}", exc_info=True)
            raise SearchError(
                "SEARCH_ERROR",
                f"搜索过程中发生错误: {str(e)}",
                detail=str(e)
            )
    
    def _parse_research_output(
        self,
        output: Any,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        解析研究输出为搜索结果
        
        研究客户端返回的是文本内容，需要解析为结构化结果
        """
        results = []
        
        # 获取内容
        content = output.content or ""
        
        if not content:
            return results
        
        # 尝试解析内容
        # 博查返回格式: [1] 标题\n来源: xxx\n摘要: xxx\n链接: xxx\n\n[2] ...
        items = content.split("\n\n")
        
        for item_text in items[:max_results]:
            if not item_text.strip():
                continue
            
            lines = item_text.strip().split("\n")
            if not lines:
                continue
            
            # 提取标题（第一行，去掉 [数字] 前缀）
            title_line = lines[0]
            title = title_line
            if title_line.startswith("[") and "]" in title_line:
                title = title_line.split("]", 1)[1].strip()
            
            # 提取其他字段
            source = None
            snippet = None
            url = None
            published_date = None
            
            for line in lines[1:]:
                if line.startswith("来源:") or line.startswith("来源："):
                    source = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
                elif line.startswith("发布时间:") or line.startswith("发布时间："):
                    published_date = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
                elif line.startswith("摘要:") or line.startswith("摘要："):
                    snippet = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
                elif line.startswith("简介:") or line.startswith("简介："):
                    if not snippet:
                        snippet = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
                elif line.startswith("链接:") or line.startswith("链接："):
                    url = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
            
            # 如果没有摘要，使用标题
            if not snippet:
                snippet = title
            
            # 如果没有 URL，使用占位符
            if not url:
                url = f"https://search.result/{len(results) + 1}"
            
            result = self._normalize_result({
                "title": title,
                "snippet": snippet,
                "url": url,
                "source": source,
                "published_date": published_date,
                "score": 0.8 - len(results) * 0.05,  # 简单的评分
            })
            
            results.append(result)
        
        # 如果解析失败，返回一个包含原始内容的结果
        if not results and content:
            results.append(self._normalize_result({
                "title": f"搜索结果",
                "snippet": content[:200],
                "url": "https://search.result/1",
                "source": self.provider_name,
            }))
        
        return results
    
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        return f"unified-{self.provider_name}"
