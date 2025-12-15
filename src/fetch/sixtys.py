from __future__ import annotations

import hashlib
import logging
from typing import Any

import requests


def _stable_item_id(source: str, date: str, idx: int, title: str, link: str) -> str:
    base = f"{source}|{date}|{idx}|{title}|{link}".strip()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _get_str(d: dict[str, Any], key: str) -> str:
    v = d.get(key)
    return v.strip() if isinstance(v, str) else ""


def fetch_sixtys_items_with_status(
    *,
    base_url: str | None = None,
    base_urls: list[str] | None = None,
    source: str,
    timeout_seconds: int,
) -> tuple[list[dict], int | None, str | None]:
    log = logging.getLogger("fetch.sixtys")

    candidates: list[str] = []
    if isinstance(base_urls, list):
        for u in base_urls:
            if isinstance(u, str) and u.strip():
                candidates.append(u.strip())
    if base_url and base_url.strip():
        candidates.append(base_url.strip())
    if not candidates:
        raise RuntimeError("sixtys base_url(s) empty")

    last_status: int | None = None
    last_err: Exception | None = None

    for cand in candidates:
        u0 = cand.rstrip("/")
        if not (u0.startswith("http://") or u0.startswith("https://")):
            u0 = "https://" + u0

        url = f"{u0}/v2/60s"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Referer": f"{u0}/",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=timeout_seconds)
            last_status = int(getattr(resp, "status_code", 0) or 0) or None
            if resp.status_code == 403:
                log.warning("sixtys returned 403 (Forbidden). base_url=%s", u0)
                continue
            resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, dict):
                continue

            payload = data.get("data")
            if not isinstance(payload, dict):
                continue

            date = _get_str(payload, "date")
            link = _get_str(payload, "link")
            published_at = date or None

            news = payload.get("news")
            if not isinstance(news, list):
                continue

            out: list[dict] = []
            for i, s in enumerate(news):
                if not isinstance(s, str):
                    continue
                title = s.strip()
                if not title:
                    continue
                out.append(
                    {
                        "id": _stable_item_id(source=source, date=date or "", idx=i, title=title, link=link),
                        "title": title,
                        "summary": "",
                        "content": "",
                        "url": link or url,
                        "published_at": published_at,
                        "source": source,
                    }
                )

            tip = _get_str(payload, "tip")
            if tip:
                out.append(
                    {
                        "id": _stable_item_id(source=source, date=date or "", idx=999, title=tip, link=link),
                        "title": tip,
                        "summary": "",
                        "content": "",
                        "url": link or url,
                        "published_at": published_at,
                        "source": source,
                    }
                )

            return out, int(resp.status_code), u0
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue

    if last_err is not None:
        raise last_err
    return [], last_status, None
