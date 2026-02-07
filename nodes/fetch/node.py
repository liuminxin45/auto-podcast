from typing import Dict, Any, List
from nodes.fetch.config import FetchConfig


def run(state: Dict[str, Any], config: FetchConfig = None) -> Dict[str, Any]:
    config = config or FetchConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[FetchNode] Starting fetch")
    raw_contents = []

    try:
        for source in config.sources:
            source_type = source.get("type", "rss")
            source_url = source.get("url", "")
            if not source_url:
                continue

            if source_type == "rss":
                items = _fetch_rss(source_url)
            elif source_type == "web":
                items = _fetch_web(source_url, config)
            else:
                logs.append(f"[FetchNode] Unknown source type: {source_type}")
                continue

            raw_contents.extend(items[:config.max_items_per_source])
    except Exception as e:
        errors.append({"node": "fetch", "message": f"Fetch failed: {str(e)}", "detail": str(e)})

    state["raw_contents"] = raw_contents
    logs.append(f"[FetchNode] Fetched {len(raw_contents)} items")
    state["logs"] = logs
    state["errors"] = errors
    return state


def _fetch_rss(url: str) -> List[Dict[str, Any]]:
    import feedparser
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        items.append({
            "title": entry.get("title", ""),
            "content": entry.get("summary", ""),
            "url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source": url,
            "type": "rss",
        })
    return items


def _fetch_web(url: str, config: FetchConfig) -> List[Dict[str, Any]]:
    import requests
    from trafilatura import extract
    response = requests.get(url, timeout=config.timeout, headers={"User-Agent": config.user_agent})
    content = extract(response.text)
    return [{
        "title": "",
        "content": content or "",
        "url": url,
        "published": "",
        "source": url,
        "type": "web",
    }]
