from __future__ import annotations

import hashlib


def _fingerprint(item: dict) -> str:
    base = (item.get("url") or "") + "|" + (item.get("title") or "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def dedup_items(items: list[dict], max_items: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    for it in items:
        fp = _fingerprint(it)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(it)
        if len(out) >= max_items:
            break

    return out
