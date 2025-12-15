from __future__ import annotations

import re


_CALENDAR_TITLE_RE = re.compile(r"^[📅🗓]\s*\d{4}-\d{2}-\d{2}\s+星期[一二三四五六日天]$")


def _is_noise_item(item: dict) -> bool:
    title = (item.get("title") or "").strip()
    if not title:
        return False
    if _CALENDAR_TITLE_RE.match(title):
        return True
    return False


def filter_items(items: list[dict], fields: list[str] | None) -> list[dict]:
    if fields is None:
        fields = ["title"]

    fields2 = [str(f).strip() for f in fields if str(f).strip()]
    if "url" not in fields2:
        fields2.append("url")
    if not fields2:
        return list(items)

    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if _is_noise_item(it):
            continue
        o: dict = {}
        for f in fields2:
            o[f] = it.get(f)
        out.append(o)
    return out


def filter_fetch_archive_payload(payload: dict, fields: list[str] | None, keep_raw: bool = False) -> dict:
    if not isinstance(payload, dict):
        return payload

    out = dict(payload)

    items_raw = payload.get("items_raw")
    items_raw2 = [x for x in items_raw if isinstance(x, dict)] if isinstance(items_raw, list) else None

    if isinstance(items_raw2, list):
        out["raw_items_count"] = len(items_raw2)

    if keep_raw:
        if isinstance(items_raw2, list):
            out["items_raw"] = filter_items(items_raw2, fields)
    else:
        out.pop("items_raw", None)

    items = payload.get("items")
    if not keep_raw and isinstance(items_raw2, list):
        filtered_items = filter_items(items_raw2, fields)
        out["items"] = filtered_items
        out["filtered_items_count"] = len(filtered_items)
    elif isinstance(items, list):
        filtered_items = filter_items([x for x in items if isinstance(x, dict)], fields)
        out["items"] = filtered_items
        out["filtered_items_count"] = len(filtered_items)

    return out
