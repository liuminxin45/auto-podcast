from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlencode

from src.fetch.rss import fetch_rss_items


def _bool_to_str(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _build_query(query: dict[str, Any] | None) -> str:
    if not query:
        return ""
    pairs: list[tuple[str, str]] = []
    for k, v in query.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            for x in v:
                if x is None:
                    continue
                pairs.append((str(k), _bool_to_str(x)))
        else:
            pairs.append((str(k), _bool_to_str(v)))
    if not pairs:
        return ""
    return "?" + urlencode(pairs)


def _extract(kind: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("empty input")

    if kind == "zhihuzhuanlan":
        m = re.search(r"https?://zhuanlan\.zhihu\.com/([^/?#]+)", v)
        if m:
            return m.group(1)
        m = re.search(r"https?://www\.zhihu\.com/column/([^/?#]+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind in {"zhihu", "zhihu_upvote"}:
        m = re.search(r"https?://www\.zhihu\.com/(?:people|org)/([^/?#]+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "zhihu_topic":
        m = re.search(r"https?://www\.zhihu\.com/topic/(\d+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "zhihu_question":
        m = re.search(r"https?://www\.zhihu\.com/question/(\d+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "zhihu_collection":
        m = re.search(r"https?://www\.zhihu\.com/collection/(\d+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "v2ex":
        m = re.search(r"https?://www\.v2ex\.com/t/(\d+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "static_zhihu":
        m = re.search(r"https?://zhuanlan\.zhihu\.com/p/(\d+)", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind in {"jike_topic", "jike_user"}:
        m = re.search(r"https?://[^/]+/([^/?#]+)$", v)
        if m:
            return m.group(1)
        return v.strip("/")

    if kind == "gogs":
        m = re.search(r"https?://(.+)$", v)
        if m:
            return m.group(1)
        return v.lstrip("/")

    return v.strip("/")


def build_lily_rss_url(
    *,
    kind: str,
    value: str,
    base_url: str = "https://rss.lilydjwg.me",
    query: Optional[dict[str, Any]] = None,
) -> str:
    k = (kind or "").strip()
    if not k:
        raise ValueError("kind is empty")
    b = (base_url or "").rstrip("/")
    if not b:
        raise ValueError("base_url is empty")

    ident = _extract(k, value)
    q = _build_query(query)
    return f"{b}/{k}/{ident}{q}"


def fetch_lily_rss_items(
    *,
    kind: str,
    value: str,
    source: str,
    timeout_seconds: int,
    base_url: str = "https://rss.lilydjwg.me",
    query: Optional[dict[str, Any]] = None,
) -> list[dict]:
    feed_url = build_lily_rss_url(kind=kind, value=value, base_url=base_url, query=query)
    return fetch_rss_items(url=feed_url, source=source, timeout_seconds=timeout_seconds)
