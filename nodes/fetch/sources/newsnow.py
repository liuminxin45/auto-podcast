"""
NewsNow 多平台热榜聚合数据源

通过 TrendRadar (engine/trendradar) 的 DataFetcher 抓取全网热榜。
TrendRadar 作为完全隔离的子系统，本文件仅通过 engine.bridge 与其通信。

平台列表和 API 逻辑全部由 TrendRadar 管理，
本 source 只负责调用 bridge 并返回标准格式数据。
"""
from typing import List, Dict, Any, Optional
from nodes.fetch.sources.base import FetchSourceBase


class NewsNowSource(FetchSourceBase):
    """
    全网热榜数据源 — 由 TrendRadar 驱动。

    数据流：
        TrendRadar DataFetcher  →  engine.bridge  →  本 source  →  fetch 节点
    """

    def __init__(
        self,
        platform_ids: Optional[List[str]] = None,
        max_items_per_platform: int = 30,
        proxy_url: Optional[str] = None,
        api_url: Optional[str] = None,
        request_interval: int = 100,
    ):
        self._platform_ids = platform_ids
        self._max_items = max_items_per_platform
        self._proxy_url = proxy_url
        self._api_url = api_url
        self._request_interval = request_interval

    @property
    def name(self) -> str:
        return "全网热榜 (TrendRadar)"

    @property
    def description(self) -> str:
        from engine.bridge import load_trendradar_platforms
        platforms = load_trendradar_platforms()
        count = len(self._platform_ids) if self._platform_ids else len(platforms)
        return f"聚合 {count} 个平台的实时热榜（今日头条/百度/微博/知乎/抖音/B站等）"

    def fetch(self, fetch_logs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """通过 TrendRadar bridge 拉取热榜数据。"""
        from engine.bridge import fetch_trending_as_items

        return fetch_trending_as_items(
            platform_ids=self._platform_ids,
            max_items_per_platform=self._max_items,
            proxy_url=self._proxy_url,
            api_url=self._api_url,
            request_interval=self._request_interval,
            fetch_logs=fetch_logs,
        )

    @staticmethod
    def get_all_platforms() -> List[Dict[str, str]]:
        """返回 TrendRadar config.yaml 中所有可用平台。"""
        from engine.bridge import load_trendradar_platforms
        return load_trendradar_platforms()


# 导出实例供 fetch 节点使用
source = NewsNowSource()
