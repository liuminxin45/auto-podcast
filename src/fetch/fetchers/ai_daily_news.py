"""
AI Daily News API Fetcher
Fetches AI news from https://60s.viki.moe/v2/ai-news API
"""

import hashlib
import logging
from datetime import date
from typing import Optional

import requests

from ..core.base import BaseFetcher, FetchResult, FetchStatus
from ..core.registry import register_fetcher


@register_fetcher("ai_daily_news")
class AIDailyNewsFetcher(BaseFetcher):
    """AI 日报快讯 Fetcher - 基于 API"""
    
    def __init__(self):
        self.logger = logging.getLogger("fetch.ai_daily_news")
    
    @property
    def fetcher_type(self) -> str:
        return "ai_daily_news"
    
    def validate_config(self, config: dict) -> bool:
        """验证配置"""
        if "url" not in config and "urls" not in config:
            self.logger.error("Missing 'url' or 'urls' in config")
            return False
        return True
    
    def fetch_items(
        self,
        config: dict,
        episode_date: date,
        timeout_seconds: int = 30
    ) -> FetchResult:
        """拉取 AI 日报快讯数据"""
        from src.utils.logging_config import log_operation, log_api_call
        
        # 获取API URL
        url = config.get("url")
        urls = config.get("urls", [])
        base_url = url if url else (urls[0] if urls else None)
        
        if not base_url:
            log_operation(
                self.logger,
                step="Fetch",
                operation="ai_daily_news_no_url",
                result="No URL provided"
            )
            return FetchResult(
                items=[],
                status=FetchStatus.FAILED,
                error_message="No URL provided"
            )
        
        source_name = config.get("name", "AI日报快讯")
        
        try:
            # 构建API请求URL，传入日期参数
            api_url = f"{base_url.rstrip('/')}/v2/ai-news"
            params = {
                "date": episode_date.strftime("%Y-%m-%d"),
                "encoding": "json"
            }
            
            log_operation(
                self.logger,
                step="Fetch",
                operation="ai_daily_news_start",
                result=f"source={source_name}, url={api_url}, date={params['date']}"
            )
            
            # 发起HTTP请求
            resp = requests.get(
                api_url,
                params=params,
                timeout=timeout_seconds,
                headers={"User-Agent": "podcast-bot/1.0"}
            )
            resp.raise_for_status()
            
            # 解析JSON响应
            data = resp.json()
            
            # 验证响应格式
            if data.get("code") != 200:
                error_msg = data.get("message", "Unknown error")
                log_operation(
                    self.logger,
                    step="Fetch",
                    operation="ai_daily_news_api_error",
                    result=f"API error: {error_msg}"
                )
                return FetchResult(
                    items=[],
                    status=FetchStatus.FAILED,
                    error_message=error_msg
                )
            
            # 提取新闻数据
            news_data = data.get("data", {})
            news_list = news_data.get("news", [])
            
            if not news_list:
                log_operation(
                    self.logger,
                    step="Fetch",
                    operation="ai_daily_news_no_items",
                    result=f"No news items for date {episode_date}"
                )
                return FetchResult(
                    items=[],
                    status=FetchStatus.SUCCESS,
                    metadata={"url": api_url, "date": episode_date.isoformat()}
                )
            
            # 转换为标准格式
            items = []
            for news_item in news_list:
                item = self._parse_news_item(news_item, source_name, episode_date)
                if item:
                    items.append(item)
            
            log_operation(
                self.logger,
                step="Fetch",
                operation="ai_daily_news_success",
                result=f"{len(items)} items from {source_name}"
            )
            
            return FetchResult(
                items=items,
                status=FetchStatus.SUCCESS,
                metadata={
                    "url": api_url,
                    "date": episode_date.isoformat(),
                    "total_news": len(news_list)
                }
            )
            
        except requests.Timeout:
            self.logger.error(f"Timeout fetching {source_name}")
            return FetchResult(items=[], status=FetchStatus.TIMEOUT)
        
        except requests.RequestException as e:
            self.logger.error(f"Request failed for {source_name}: {e}")
            return FetchResult(
                items=[],
                status=FetchStatus.FAILED,
                error_message=str(e)
            )
        
        except Exception as e:
            self.logger.error(f"Failed to fetch {source_name}: {e}")
            return FetchResult(
                items=[],
                status=FetchStatus.FAILED,
                error_message=str(e)
            )
    
    def _parse_news_item(
        self,
        news_item: dict,
        source_name: str,
        item_date: date
    ) -> Optional[dict]:
        """解析单个新闻item"""
        
        title = news_item.get("title", "").strip()
        detail = news_item.get("detail", "").strip()
        link = news_item.get("link", "").strip()
        source = news_item.get("source", "").strip()
        
        if not title or not link:
            self.logger.debug(f"Skipping item with missing title or link")
            return None
        
        # 生成稳定ID（基于link）
        item_id = hashlib.sha256(link.encode()).hexdigest()[:16]
        
        # 组合内容：detail作为主要内容
        content = detail if detail else title
        
        # 如果有来源信息，添加到内容中
        if source and source != source_name:
            content = f"[来源: {source}] {content}"
        
        return {
            "id": item_id,
            "title": title,
            "summary": detail[:200] if detail else title,
            "content": content,
            "url": link,
            "published_at": item_date.isoformat(),
            "source": source_name,
            "metadata": {
                "original_source": source,
                "api_date": news_item.get("date", "")
            }
        }
