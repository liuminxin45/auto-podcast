from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import logging
from typing import Any, Optional

import requests


def _stable_item_id(source_id: str, url: str, native_id: Optional[str]) -> str:
    base = f"{source_id}|{native_id or ''}|{url}".strip()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _to_iso8601(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str) and value.strip():
        s = value.strip()
        if s.isdigit():
            try:
                n = int(s)
                return _to_iso8601(n)
            except Exception:
                return s
        return s

    if isinstance(value, (int, float)):
        n = float(value)
        # Heuristic: ms vs seconds
        if n > 1e12:
            n = n / 1000.0
        try:
            return dt.datetime.fromtimestamp(n, tz=dt.timezone.utc).isoformat()
        except Exception:
            return None

    return None


def fetch_newsnow_items(
    *,
    base_url: str,
    source_id: str,
    source: str,
    timeout_seconds: int,
    count: int = 10,
) -> list[dict]:
    items, _status = fetch_newsnow_items_with_status(
        base_url=base_url,
        source_id=source_id,
        source=source,
        timeout_seconds=timeout_seconds,
        count=count,
    )
    return items


def fetch_newsnow_items_with_status(
    *,
    base_url: str,
    source_id: str,
    source: str,
    timeout_seconds: int,
    count: int = 10,
) -> tuple[list[dict], int | None]:
    log = logging.getLogger("fetch.newsnow")
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("newsnow base_url is empty")
    if not source_id:
        raise RuntimeError("newsnow source_id is empty")

    url = f"{base_url}/api/s"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": f"{base_url}/",
    }

    resp = requests.get(url, params={"id": source_id}, headers=headers, timeout=timeout_seconds)
    if resp.status_code == 403:
        log.warning(
            "newsnow returned 403 (Forbidden). The public instance may block scraping; base_url=%s source_id=%s",
            base_url,
            source_id,
        )
        return [], int(resp.status_code)
    resp.raise_for_status()

    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("newsnow response is not json: %s", e)
        return [], int(getattr(resp, "status_code", 0) or 0) or None
    items = data.get("items") or []
    if not isinstance(items, list):
        log.warning("unexpected newsnow response items type=%s", type(items))
        return [], int(resp.status_code)

    out: list[dict] = []
    for it in items[: max(1, int(count or 10))]:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        link = (it.get("url") or "").strip()
        if not link:
            continue

        native_id = it.get("id")
        native_id_s = str(native_id) if native_id is not None else None
        published_at = _to_iso8601(it.get("pubDate"))
        extra_raw = it.get("extra")
        extra: dict[str, Any] = extra_raw if isinstance(extra_raw, dict) else {}
        published_at = published_at or _to_iso8601(extra.get("date"))

        out.append(
            {
                "id": _stable_item_id(source_id=source_id, url=link, native_id=native_id_s),
                "title": title,
                "summary": "",
                "content": "",
                "url": link,
                "published_at": published_at,
                "source": source,
            }
        )

    return out, int(resp.status_code)


def fetch_newsnow_sources_catalog(*, timeout_seconds: int = 20) -> dict[str, dict[str, Any]]:
    url = "https://api.github.com/repos/ourongxing/newsnow/contents/shared/sources.json"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "auto-podcast/1.0",
    }
    resp = requests.get(url, params={"ref": "main"}, headers=headers, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("unexpected github response for sources.json")

    content_b64 = data.get("content")
    if not isinstance(content_b64, str) or not content_b64.strip():
        raise RuntimeError("github sources.json content missing")

    raw = base64.b64decode(content_b64.encode("utf-8"))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected sources.json payload")

    out: dict[str, dict[str, Any]] = {}
    for k, v in payload.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, dict):
            out[k] = v
    return out


def probe_newsnow_source_id(
    *,
    base_url: str,
    source_id: str,
    timeout_seconds: int,
) -> tuple[bool, int | None, str | None]:
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("newsnow base_url is empty")
    if not source_id:
        raise RuntimeError("newsnow source_id is empty")

    url = f"{base_url}/api/s"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": f"{base_url}/",
    }
    try:
        resp = requests.get(url, params={"id": source_id}, headers=headers, timeout=timeout_seconds)
    except Exception as e:  # noqa: BLE001
        return False, None, str(e)

    sc = int(getattr(resp, "status_code", 0) or 0) or None
    if sc != 200:
        return False, sc, None

    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        return False, sc, f"invalid json: {e}"

    if isinstance(data, dict) and "items" in data:
        return True, sc, None
    return False, sc, None
