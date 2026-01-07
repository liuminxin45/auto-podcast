import hashlib
import logging
from datetime import date
from typing import Any, Optional

import requests

from ..core.base import BaseFetcher, FetchResult, FetchStatus
from ..core.registry import register_fetcher


@register_fetcher("today_in_history")
class TodayInHistoryFetcher(BaseFetcher):
    def __init__(self) -> None:
        self.logger = logging.getLogger("fetch.today_in_history")

    @property
    def fetcher_type(self) -> str:
        return "today_in_history"

    def validate_config(self, config: dict) -> bool:
        if "url" not in config and "base_url" not in config:
            self.logger.error("Missing 'url' or 'base_url' in config")
            return False
        return True

    def fetch_items(
        self,
        config: dict,
        episode_date: date,
        timeout_seconds: int = 30,
    ) -> FetchResult:
        from src.utils.logging_config import log_operation

        source_name = (config.get("name") or "today-in-history").strip()
        url = (config.get("url") or "").strip()
        if not url:
            base_url = (config.get("base_url") or "").strip()
            if base_url:
                url = f"{base_url.rstrip('/')}/v2/today-in-history"

        if not url:
            return FetchResult(items=[], status=FetchStatus.FAILED, error_message="No URL provided")

        params = dict(config.get("params") or {})
        params.setdefault("encoding", "json")

        log_operation(
            self.logger,
            step="Fetch",
            operation="today_in_history_start",
            result=f"source={source_name}",
        )

        try:
            resp = requests.get(
                url,
                params=params,
                timeout=timeout_seconds,
                headers={"User-Agent": "podcast-bot/1.0"},
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()

            data = payload.get("data") or {}
            items = data.get("items") or []
            if not isinstance(items, list):
                return FetchResult(
                    items=[],
                    status=FetchStatus.FAILED,
                    error_message="Invalid response: data.items is not a list",
                )

            out_items: list[dict] = []
            published_at = f"{episode_date.isoformat()}T00:00:00+00:00"
            api_date = (data.get("date") or "").strip()

            for it in items:
                if not isinstance(it, dict):
                    continue
                title = (it.get("title") or "").strip()
                year = str(it.get("year") or "").strip()
                description = (it.get("description") or "").strip()
                event_type = (it.get("event_type") or "").strip()
                link = (it.get("link") or "").strip()

                if not title or not description:
                    continue

                stable = f"{api_date}|{year}|{title}|{event_type}|{link}".encode("utf-8")
                item_id = hashlib.sha256(stable).hexdigest()[:16]

                out_items.append(
                    {
                        "id": item_id,
                        "title": f"{year}年：{title}" if year else title,
                        "summary": description,
                        "content": description,
                        "url": link or url,
                        "published_at": published_at,
                        "source": source_name,
                        "category": "history",
                        "_metadata": {
                            "year": year,
                            "event_type": event_type,
                            "api_date": api_date,
                        },
                    }
                )

            if not out_items:
                return FetchResult(items=[], status=FetchStatus.FAILED, error_message="No valid history items")

            return FetchResult(
                items=out_items,
                status=FetchStatus.SUCCESS,
                metadata={"url": url, "api_date": api_date, "item_count": len(out_items)},
            )

        except requests.Timeout:
            return FetchResult(items=[], status=FetchStatus.TIMEOUT)
        except Exception as e:
            self.logger.error(f"Failed to fetch today-in-history: {e}")
            return FetchResult(items=[], status=FetchStatus.FAILED, error_message=str(e))
