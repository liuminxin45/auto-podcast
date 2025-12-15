from __future__ import annotations

import datetime as dt
import hashlib
import logging
from typing import Any

import feedparser
import requests


def _to_iso8601(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc).isoformat()
        return value.isoformat()

    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc).isoformat()

    return None


def _stable_item_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def fetch_rss_items(url: str, source: str, timeout_seconds: int) -> list[dict]:
    items, _status = fetch_rss_items_with_status(url=url, source=source, timeout_seconds=timeout_seconds)
    return items


def fetch_rss_items_with_status(url: str, source: str, timeout_seconds: int) -> tuple[list[dict], int]:
    log = logging.getLogger("fetch.rss")

    resp = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "podcast-bot/0.1"},
    )
    resp.raise_for_status()

    parsed = feedparser.parse(resp.content)
    if getattr(parsed, "bozo", 0):
        log.warning("rss parse bozo=%s error=%s", parsed.bozo, getattr(parsed, "bozo_exception", None))

    out: list[dict] = []
    for e in getattr(parsed, "entries", []) or []:
        link = (getattr(e, "link", None) or "").strip()
        if not link:
            continue

        title = (getattr(e, "title", None) or "").strip()
        summary = (getattr(e, "summary", None) or "").strip()

        content = ""
        content_list = getattr(e, "content", None)
        if isinstance(content_list, list) and content_list:
            content = (content_list[0].get("value") or "").strip()

        published_at = None
        if getattr(e, "published", None):
            published_at = _to_iso8601(getattr(e, "published", None))
        if not published_at and getattr(e, "published_parsed", None):
            t = getattr(e, "published_parsed")
            published_at = dt.datetime(*t[:6], tzinfo=dt.timezone.utc).isoformat()

        out.append(
            {
                "id": _stable_item_id(link),
                "title": title,
                "summary": summary,
                "content": content,
                "url": link,
                "published_at": published_at,
                "source": source,
            }
        )

    return out, int(resp.status_code)
