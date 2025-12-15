from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from src.audio.render import render_episode_audio
from src.fetch.dedup import dedup_items
from src.fetch.lilyrss import build_lily_rss_url
from src.fetch.newsnow import fetch_newsnow_items_with_status, fetch_newsnow_sources_catalog, probe_newsnow_source_id
from src.fetch.rss import fetch_rss_items_with_status
from src.fetch.sixtys import fetch_sixtys_items_with_status
from src.script.deepseek import DeepSeekClient, ScriptInputItem, ScriptOutput
from src.store.db import Store
from src.publish.local import publish_local
from src.filter import filter_fetch_archive_payload
from src.research.metaso import metaso_research_items


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, object] = {
            "ts": dt.datetime.fromtimestamp(record.created, tz=dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        msg_obj: object
        try:
            msg_obj = record.msg
        except Exception:
            msg_obj = None

        if isinstance(msg_obj, dict):
            base.update(msg_obj)
        else:
            base["message"] = record.getMessage()

        ev = getattr(record, "event", None)
        if isinstance(ev, dict):
            base.update(ev)
        elif ev is not None:
            base["event"] = ev

        return json.dumps(base, ensure_ascii=False)


def _log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    payload: dict[str, object] = {"event": event}
    payload.update(fields)
    logger.info("event", extra={"event": payload})


def _load_yaml(path: Path) -> dict:
    import yaml

    raw = path.read_text(encoding="utf-8")

    def _expand_env(s: str) -> str:
        out = ""
        i = 0
        while i < len(s):
            if s[i : i + 2] == "${":
                j = s.find("}", i + 2)
                if j == -1:
                    out += s[i:]
                    break
                key = s[i + 2 : j]
                out += os.environ.get(key, "")
                i = j + 1
            else:
                out += s[i]
                i += 1
        return out

    raw = _expand_env(raw)
    return yaml.safe_load(raw) or {}


def _setup_logging(log_dir: Path, episode_date: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{episode_date}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt_kind = (os.environ.get("LOG_FORMAT") or "text").strip().lower()
    if fmt_kind == "json":
        fmt: logging.Formatter = _JsonFormatter()
    else:
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)

    root.handlers.clear()
    root.addHandler(sh)
    root.addHandler(fh)


def _today_str() -> str:
    return dt.date.today().isoformat()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = 0
    for ch in text:
        o = ord(ch)
        if (
            0x4E00 <= o <= 0x9FFF
            or 0x3400 <= o <= 0x4DBF
            or 0x20000 <= o <= 0x2A6DF
            or 0x2A700 <= o <= 0x2B73F
            or 0x2B740 <= o <= 0x2B81F
            or 0x2B820 <= o <= 0x2CEAF
        ):
            cjk += 1
    other = max(0, len(text) - cjk)
    return int(cjk + (other / 4.0))


def _calc_items_text_stats(items: list[dict]) -> tuple[int, int, int, int]:
    total_chars = 0
    total_tokens = 0
    max_item_chars = 0
    max_item_tokens = 0
    for it in items:
        s = (it.get("title") or "") + "\n" + (it.get("summary") or "") + "\n" + (it.get("content") or "")
        c = len(s)
        t = _estimate_tokens(s)
        total_chars += c
        total_tokens += t
        if c > max_item_chars:
            max_item_chars = c
        if t > max_item_tokens:
            max_item_tokens = t
    return total_chars, total_tokens, max_item_chars, max_item_tokens


def _apply_category(items: list[dict], category: str) -> None:
    cat = (category or "").strip() or "others"
    for it in items:
        if isinstance(it, dict) and "category" not in it:
            it["category"] = cat


def _archive_fetch_result(
    *,
    archive_base_dir: Path,
    episode_date: str,
    prefix: str,
    payload: dict,
) -> Path:
    try:
        d = dt.date.fromisoformat(episode_date)
    except Exception:
        d = dt.date.today()

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = archive_base_dir / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{prefix}_{ts}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def step_fetch(store: Store, cfg: dict, episode_id: str, timeout_s: int, force_fetch: bool) -> None:
    log = logging.getLogger("step.fetch")

    ep = store.get_episode(episode_id)
    if (not force_fetch) and ep["status"] in {"fetched", "scripted", "tts_done", "rendered", "published"}:
        log.info("episode already fetched or later; skip")
        return

    rss_sources = (cfg.get("sources") or {}).get("rss") or []
    newsnow_sources = (cfg.get("sources") or {}).get("newsnow") or []
    sixtys_sources = (cfg.get("sources") or {}).get("sixtys") or []
    lily_sources_raw = (cfg.get("sources") or {}).get("lily_rss") or []
    newsnow_force_enable_all = bool(((cfg.get("sources") or {}).get("newsnow_force_enable_all")) or False)
    max_items = int((cfg.get("pipeline") or {}).get("max_items") or 8)

    out_cfg = cfg.get("output") or {}
    fetch_archives_dir = Path(out_cfg.get("fetch_archives_dir") or "./out/fetch_archives")

    filter_cfg = cfg.get("filter") or {}
    filter_fields = filter_cfg.get("fields")
    filter_keep_raw = bool(filter_cfg.get("keep_raw") or False)
    if filter_fields is None:
        filter_fields2: list[str] | None = None
    elif isinstance(filter_fields, list):
        filter_fields2 = [str(x) for x in filter_fields]
    else:
        filter_fields2 = None

    warn_duration_ms = int(os.environ.get("FETCH_WARN_DURATION_MS", "15000"))
    warn_total_tokens = int(os.environ.get("FETCH_HEALTH_WARN_TOTAL_TOKENS", "20000"))
    warn_max_item_tokens = int(os.environ.get("FETCH_HEALTH_WARN_MAX_ITEM_TOKENS", "8000"))

    run_id = store.create_fetch_run(episode_id)
    _log_event(
        log,
        "fetch_run_start",
        run_id=int(run_id),
        episode_id=str(episode_id),
        max_items=int(max_items),
    )
    try:
        fetched: list[dict] = []

        for src in rss_sources:
            enabled = (src or {}).get("enabled")
            if enabled is False:
                continue

            name = (src or {}).get("name") or "rss"

            category = ((src or {}).get("category") or "others").strip() or "others"
            url = (src or {}).get("url")
            urls = (src or {}).get("urls")
            candidates: list[str] = []
            if isinstance(urls, list):
                for u in urls:
                    if isinstance(u, str) and u.strip():
                        candidates.append(u.strip())
            if isinstance(url, str) and url.strip():
                candidates.append(url.strip())
            if not candidates:
                continue

            ok_any = False
            for cand in candidates:
                log.info("fetch rss: %s %s", name, cand)
                t0 = time.perf_counter()
                try:
                    items, sc = fetch_rss_items_with_status(url=cand, source=name, timeout_seconds=timeout_s)
                    _apply_category(items, category)
                    total_chars, total_tokens, max_item_chars, max_item_tokens = _calc_items_text_stats(items)
                    fetched.extend(items)
                    dur_ms = int((time.perf_counter() - t0) * 1000)
                    store.add_fetch_attempt(
                        run_id=run_id,
                        source_type="rss",
                        source_name=name,
                        url=str(cand),
                        ok=True,
                        status_code=(int(sc) if sc is not None else None),
                        error=None,
                        duration_ms=dur_ms,
                        item_count=len(items),
                        total_chars=total_chars,
                        est_tokens=total_tokens,
                        max_item_chars=max_item_chars,
                        max_item_tokens=max_item_tokens,
                    )
                    _log_event(
                        log,
                        "fetch_attempt",
                        run_id=int(run_id),
                        source_type="rss",
                        source_name=str(name),
                        url=str(cand),
                        ok=True,
                        status_code=(int(sc) if sc is not None else None),
                        duration_ms=int(dur_ms),
                        item_count=int(len(items)),
                        total_chars=int(total_chars),
                        est_tokens=int(total_tokens),
                        max_item_chars=int(max_item_chars),
                        max_item_tokens=int(max_item_tokens),
                    )
                    if len(items) == 0:
                        log.warning("fetch rss ok but 0 items: %s", name)
                    if dur_ms >= warn_duration_ms:
                        log.warning("fetch rss slow: %s ms=%s", name, dur_ms)
                    if total_tokens >= warn_total_tokens or max_item_tokens >= warn_max_item_tokens:
                        log.warning(
                            "fetch rss tokens large: %s total=%s max_item=%s",
                            name,
                            total_tokens,
                            max_item_tokens,
                        )
                    ok_any = True
                    break
                except Exception as e:  # noqa: BLE001
                    resp = getattr(e, "response", None)
                    sc2 = getattr(resp, "status_code", None)
                    dur_ms = int((time.perf_counter() - t0) * 1000)
                    store.add_fetch_attempt(
                        run_id=run_id,
                        source_type="rss",
                        source_name=name,
                        url=str(cand),
                        ok=False,
                        status_code=sc2,
                        error=str(e),
                        duration_ms=dur_ms,
                        item_count=0,
                        total_chars=0,
                        est_tokens=0,
                        max_item_chars=0,
                        max_item_tokens=0,
                    )
                    _log_event(
                        log,
                        "fetch_attempt",
                        run_id=int(run_id),
                        source_type="rss",
                        source_name=str(name),
                        url=str(cand),
                        ok=False,
                        status_code=sc2,
                        duration_ms=int(dur_ms),
                        item_count=0,
                        error=str(e),
                    )
                    log.warning("fetch rss failed: %s", e)

            if not ok_any:
                log.warning("fetch rss all candidates failed: %s", name)

        for src in sixtys_sources:
            enabled = (src or {}).get("enabled")
            if enabled is False:
                continue

            name = (src or {}).get("name") or "60s"
            base_url = ((src or {}).get("base_url") or "").strip() or "https://60s.viki.moe"
            base_urls = (src or {}).get("base_urls")
            base_urls2 = base_urls if isinstance(base_urls, list) else None
            category = ((src or {}).get("category") or "others").strip() or "others"

            log.info("fetch sixtys: %s base=%s", name, base_url)
            t0 = time.perf_counter()
            try:
                items, sc, used_base = fetch_sixtys_items_with_status(
                    base_url=base_url,
                    base_urls=base_urls2,
                    source=name,
                    timeout_seconds=timeout_s,
                )
                used_base2 = used_base or base_url
                _apply_category(items, category)
                total_chars, total_tokens, max_item_chars, max_item_tokens = _calc_items_text_stats(items)
                fetched.extend(items)
                dur_ms = int((time.perf_counter() - t0) * 1000)

                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="sixtys",
                    source_name=name,
                    url=f"{used_base2.rstrip('/')}/v2/60s",
                    ok=True,
                    status_code=(int(sc) if sc is not None else None),
                    error=None,
                    duration_ms=dur_ms,
                    item_count=len(items),
                    total_chars=total_chars,
                    est_tokens=total_tokens,
                    max_item_chars=max_item_chars,
                    max_item_tokens=max_item_tokens,
                )

                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="sixtys",
                    source_name=str(name),
                    url=f"{used_base2.rstrip('/')}/v2/60s",
                    ok=True,
                    status_code=(int(sc) if sc is not None else None),
                    duration_ms=int(dur_ms),
                    item_count=int(len(items)),
                    total_chars=int(total_chars),
                    est_tokens=int(total_tokens),
                    max_item_chars=int(max_item_chars),
                    max_item_tokens=int(max_item_tokens),
                )

                if len(items) == 0:
                    log.warning("fetch sixtys ok but 0 items: %s", name)
                if dur_ms >= warn_duration_ms:
                    log.warning("fetch sixtys slow: %s ms=%s", name, dur_ms)
                if total_tokens >= warn_total_tokens or max_item_tokens >= warn_max_item_tokens:
                    log.warning(
                        "fetch sixtys tokens large: %s total=%s max_item=%s",
                        name,
                        total_tokens,
                        max_item_tokens,
                    )
            except Exception as e:  # noqa: BLE001
                resp = getattr(e, "response", None)
                sc2 = getattr(resp, "status_code", None)
                dur_ms = int((time.perf_counter() - t0) * 1000)

                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="sixtys",
                    source_name=name,
                    url=f"{base_url.rstrip('/')}/v2/60s",
                    ok=False,
                    status_code=sc2,
                    error=str(e),
                    duration_ms=dur_ms,
                    item_count=0,
                    total_chars=0,
                    est_tokens=0,
                    max_item_chars=0,
                    max_item_tokens=0,
                )

                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="sixtys",
                    source_name=str(name),
                    url=f"{base_url.rstrip('/')}/v2/60s",
                    ok=False,
                    status_code=sc2,
                    duration_ms=int(dur_ms),
                    item_count=0,
                    error=str(e),
                )
                log.warning("fetch sixtys failed: %s", e)

        for src in newsnow_sources:
            name = (src or {}).get("name") or "newsnow"
            enabled = (src or {}).get("enabled")
            if (not newsnow_force_enable_all) and enabled is False:
                continue
            source_id = ((src or {}).get("id") or "").strip()
            base_url = ((src or {}).get("base_url") or "").strip() or os.environ.get("NEWSNOW_BASE_URL", "").strip()
            base_url = base_url or "https://newsnow.busiyi.world"
            count = int((src or {}).get("count") or 10)
            if not source_id:
                continue

            req_url = f"{base_url.rstrip('/')}/api/s?id={source_id}"
            log.info("fetch newsnow: %s id=%s base=%s", name, source_id, base_url)
            t0 = time.perf_counter()
            try:
                items, sc = fetch_newsnow_items_with_status(
                    base_url=base_url,
                    source_id=source_id,
                    source=name,
                    timeout_seconds=timeout_s,
                    count=count,
                )
                _apply_category(items, "others")
                total_chars, total_tokens, max_item_chars, max_item_tokens = _calc_items_text_stats(items)
                fetched.extend(items)
                dur_ms = int((time.perf_counter() - t0) * 1000)
                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="newsnow",
                    source_name=name,
                    url=req_url,
                    ok=True,
                    status_code=sc,
                    error=None,
                    duration_ms=dur_ms,
                    item_count=len(items),
                    total_chars=total_chars,
                    est_tokens=total_tokens,
                    max_item_chars=max_item_chars,
                    max_item_tokens=max_item_tokens,
                )
                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="newsnow",
                    source_name=str(name),
                    url=str(req_url),
                    ok=True,
                    status_code=(int(sc) if sc is not None else None),
                    duration_ms=int(dur_ms),
                    item_count=int(len(items)),
                    total_chars=int(total_chars),
                    est_tokens=int(total_tokens),
                    max_item_chars=int(max_item_chars),
                    max_item_tokens=int(max_item_tokens),
                )
                if len(items) == 0:
                    log.warning("fetch newsnow ok but 0 items: %s", name)
                if dur_ms >= warn_duration_ms:
                    log.warning("fetch newsnow slow: %s ms=%s", name, dur_ms)
                if total_tokens >= warn_total_tokens or max_item_tokens >= warn_max_item_tokens:
                    log.warning(
                        "fetch newsnow tokens large: %s total=%s max_item=%s",
                        name,
                        total_tokens,
                        max_item_tokens,
                    )
            except Exception as e:  # noqa: BLE001
                resp = getattr(e, "response", None)
                sc2 = getattr(resp, "status_code", None)
                dur_ms = int((time.perf_counter() - t0) * 1000)
                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="newsnow",
                    source_name=name,
                    url=req_url,
                    ok=False,
                    status_code=sc2,
                    error=str(e),
                    duration_ms=dur_ms,
                    item_count=0,
                    total_chars=0,
                    est_tokens=0,
                    max_item_chars=0,
                    max_item_tokens=0,
                )
                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="newsnow",
                    source_name=str(name),
                    url=str(req_url),
                    ok=False,
                    status_code=sc2,
                    duration_ms=int(dur_ms),
                    item_count=0,
                    error=str(e),
                )
                log.warning("fetch newsnow failed: %s", e)

        def _iter_lily_entries(raw: list[object]) -> list[dict]:
            out: list[dict] = []
            for x in raw:
                if not isinstance(x, dict):
                    continue
                group = (x.get("group") or "").strip()
                items = x.get("items")
                if group and isinstance(items, list):
                    if x.get("enabled") is False:
                        continue
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        it2 = dict(it)
                        it2["_group"] = group
                        out.append(it2)
                else:
                    out.append(dict(x))
            return out

        lily_entries = _iter_lily_entries(list(lily_sources_raw))
        for src in lily_entries:
            enabled = (src or {}).get("enabled")
            if enabled is False:
                continue

            group = ((src or {}).get("_group") or "").strip()
            category = group or "others"
            name0 = (src or {}).get("name") or "lilyrss"
            name = f"{group}/{name0}" if group else str(name0)

            kind = ((src or {}).get("kind") or "").strip()
            value = ((src or {}).get("value") or "").strip()
            base_url = ((src or {}).get("base_url") or "").strip() or "https://rss.lilydjwg.me"
            query = (src or {}).get("query")
            if not isinstance(query, dict):
                query = None

            if not kind or not value:
                continue

            log.info("fetch lilyrss: %s kind=%s", name, kind)
            t0 = time.perf_counter()
            try:
                feed_url = build_lily_rss_url(kind=kind, value=value, base_url=base_url, query=query)
                items, sc = fetch_rss_items_with_status(url=feed_url, source=name, timeout_seconds=timeout_s)
                _apply_category(items, category)
                total_chars, total_tokens, max_item_chars, max_item_tokens = _calc_items_text_stats(items)
                fetched.extend(items)
                dur_ms = int((time.perf_counter() - t0) * 1000)
                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="lily_rss",
                    source_name=name,
                    url=feed_url,
                    ok=True,
                    status_code=(int(sc) if sc is not None else None),
                    error=None,
                    duration_ms=dur_ms,
                    item_count=len(items),
                    total_chars=total_chars,
                    est_tokens=total_tokens,
                    max_item_chars=max_item_chars,
                    max_item_tokens=max_item_tokens,
                )
                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="lily_rss",
                    source_name=str(name),
                    url=str(feed_url),
                    ok=True,
                    status_code=(int(sc) if sc is not None else None),
                    duration_ms=int(dur_ms),
                    item_count=int(len(items)),
                    total_chars=int(total_chars),
                    est_tokens=int(total_tokens),
                    max_item_chars=int(max_item_chars),
                    max_item_tokens=int(max_item_tokens),
                )
                if len(items) == 0:
                    log.warning("fetch lilyrss ok but 0 items: %s", name)
                if dur_ms >= warn_duration_ms:
                    log.warning("fetch lilyrss slow: %s ms=%s", name, dur_ms)
                if total_tokens >= warn_total_tokens or max_item_tokens >= warn_max_item_tokens:
                    log.warning(
                        "fetch lilyrss tokens large: %s total=%s max_item=%s",
                        name,
                        total_tokens,
                        max_item_tokens,
                    )
            except Exception as e:  # noqa: BLE001
                resp = getattr(e, "response", None)
                sc2 = getattr(resp, "status_code", None)
                dur_ms = int((time.perf_counter() - t0) * 1000)
                store.add_fetch_attempt(
                    run_id=run_id,
                    source_type="lily_rss",
                    source_name=name,
                    url=str(value),
                    ok=False,
                    status_code=sc2,
                    error=str(e),
                    duration_ms=dur_ms,
                    item_count=0,
                    total_chars=0,
                    est_tokens=0,
                    max_item_chars=0,
                    max_item_tokens=0,
                )
                _log_event(
                    log,
                    "fetch_attempt",
                    run_id=int(run_id),
                    source_type="lily_rss",
                    source_name=str(name),
                    url=str(value),
                    ok=False,
                    status_code=sc2,
                    duration_ms=int(dur_ms),
                    item_count=0,
                    error=str(e),
                )
                log.warning("fetch lilyrss failed: %s", e)

        fetched_raw = list(fetched)
        fetched = dedup_items(fetched, max_items=max_items)
        upserted = store.upsert_items(fetched)
        store.set_episode_status(episode_id, "fetched")

        try:
            archive_path = _archive_fetch_result(
                archive_base_dir=fetch_archives_dir,
                episode_date=ep["episode_date"],
                prefix="rss",
                payload={
                    "episode_id": episode_id,
                    "episode_date": ep["episode_date"],
                    "run_id": run_id,
                    "created_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
                    "max_items": max_items,
                    "raw_count": len(fetched_raw),
                    "dedup_count": len(fetched),
                    "items_raw": fetched_raw,
                    "items": fetched,
                },
            )
            log.info("fetch archive saved: %s", archive_path)

            try:
                filtered_payload = filter_fetch_archive_payload(
                    json.loads(Path(archive_path).read_text(encoding="utf-8")),
                    fields=filter_fields2,
                    keep_raw=filter_keep_raw,
                )
                filtered_path = _archive_fetch_result(
                    archive_base_dir=fetch_archives_dir,
                    episode_date=ep["episode_date"],
                    prefix="rss_filtered",
                    payload=filtered_payload,
                )
                log.info("fetch filtered archive saved: %s", filtered_path)
                _log_event(
                    log,
                    "fetch_filter",
                    run_id=int(run_id),
                    archive_path=str(archive_path),
                    filtered_path=str(filtered_path),
                    fields=(filter_fields2 if filter_fields2 is not None else ["title"]),
                )

                try:
                    items2 = filtered_payload.get("items")
                    items3 = items2 if isinstance(items2, list) else []
                    research_cfg = cfg.get("research") or {}
                    metaso_cfg = research_cfg.get("metaso") if isinstance(research_cfg, dict) else None
                    metaso_cfg2 = metaso_cfg if isinstance(metaso_cfg, dict) else {}

                    r = metaso_research_items(
                        items=items3,
                        timeout_seconds=timeout_s,
                        model=(metaso_cfg2.get("model") if isinstance(metaso_cfg2.get("model"), str) else None),
                        max_items=(metaso_cfg2.get("max_items") if isinstance(metaso_cfg2.get("max_items"), int) else None),
                    )
                    if r is not None:
                        research_payload = {
                            "episode_id": episode_id,
                            "episode_date": ep["episode_date"],
                            "run_id": run_id,
                            "created_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
                            "filtered_path": str(filtered_path),
                            "raw_items_count": int(filtered_payload.get("raw_items_count") or 0),
                            "filtered_items_count": int(filtered_payload.get("filtered_items_count") or 0),
                            "metaso": r,
                        }
                        research_path = _archive_fetch_result(
                            archive_base_dir=fetch_archives_dir,
                            episode_date=ep["episode_date"],
                            prefix="rss_research",
                            payload=research_payload,
                        )
                        log.info("fetch research archive saved: %s", research_path)
                        _log_event(
                            log,
                            "fetch_research",
                            run_id=int(run_id),
                            filtered_path=str(filtered_path),
                            research_path=str(research_path),
                            ok=bool(r.get("ok")),
                            status=(r.get("status")),
                        )
                except Exception as e:  # noqa: BLE001
                    log.warning("metaso research failed: %s", e)
            except Exception as e:  # noqa: BLE001
                log.warning("fetch filter failed: %s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("fetch archive failed: %s", e)

        log.info("items fetched=%d upserted=%d", len(fetched), upserted)
    finally:
        try:
            store.finish_fetch_run(run_id)
        except Exception:
            pass

        _log_event(
            log,
            "fetch_run_finish",
            run_id=int(run_id),
            episode_id=str(episode_id),
        )


def step_list_fetch_health_trend(store: Store, days: int, limit: int) -> None:
    log = logging.getLogger("step.list_fetch_health_trend")
    since_s = int(time.time()) - max(1, int(days or 7)) * 86400
    limit2 = max(1, int(limit or 200))

    with store._connect() as con:  # noqa: SLF001
        rows = con.execute(
            """
            SELECT date(created_at, 'unixepoch') AS d,
                   source_type,
                   source_name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN ok=1 AND item_count=0 THEN 1 ELSE 0 END) AS ok_zero,
                   AVG(duration_ms) AS avg_ms,
                   MAX(duration_ms) AS max_ms,
                   SUM(est_tokens) AS est_tokens
            FROM fetch_attempts
            WHERE created_at >= ?
            GROUP BY d, source_type, source_name
            ORDER BY d DESC, failed DESC, total DESC
            LIMIT ?
            """.strip(),
            (since_s, limit2),
        ).fetchall()

        log.info("fetch health trend rows=%d since=%s", len(rows), dt.datetime.fromtimestamp(since_s).isoformat())
        for r in rows:
            log.info(
                "trend: day=%s type=%s name=%s total=%s failed=%s ok_zero=%s avg_ms=%s max_ms=%s est_tokens=%s",
                r[0],
                r[1],
                r[2],
                r[3] or 0,
                r[4] or 0,
                r[5] or 0,
                int(r[6] or 0),
                r[7] or 0,
                r[8] or 0,
            )


def step_list_fetch_health(store: Store, cfg: dict, days: int, limit: int, only_failed: bool) -> None:
    log = logging.getLogger("step.list_fetch_health")
    since_s = int(time.time()) - max(1, int(days or 7)) * 86400
    limit2 = max(1, int(limit or 50))

    warn_total_tokens = int(os.environ.get("FETCH_HEALTH_WARN_TOTAL_TOKENS", "20000"))
    warn_max_item_tokens = int(os.environ.get("FETCH_HEALTH_WARN_MAX_ITEM_TOKENS", "8000"))

    cond = "created_at >= ?"
    params: list[object] = [since_s]
    if only_failed:
        cond += " AND ok = 0"

    with store._connect() as con:  # noqa: SLF001
        rows = con.execute(
            f"""
            SELECT source_type, source_name, COUNT(*) AS total,
                   SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS failed,
                   SUM(total_chars) AS total_chars,
                   SUM(est_tokens) AS est_tokens,
                   MAX(max_item_chars) AS max_item_chars,
                   MAX(max_item_tokens) AS max_item_tokens,
                   MAX(created_at) AS last_ts
            FROM fetch_attempts
            WHERE {cond}
            GROUP BY source_type, source_name
            ORDER BY failed DESC, total DESC
            LIMIT ?
            """.strip(),
            tuple(params + [limit2]),
        ).fetchall()

        log.info("fetch health sources=%d since=%s", len(rows), dt.datetime.fromtimestamp(since_s).isoformat())
        for r in rows:
            last_iso = dt.datetime.fromtimestamp(int(r[8])).isoformat() if r[8] else ""
            total_tokens = int(r[5] or 0)
            max_item_tokens = int(r[7] or 0)
            msg = (
                "source: type=%s name=%s total=%d failed=%d total_chars=%s est_tokens=%s max_item_chars=%s max_item_tokens=%s last=%s"
            )
            args = (r[0], r[1], r[2], r[3] or 0, r[4] or 0, total_tokens, r[6] or 0, max_item_tokens, last_iso)
            if total_tokens >= warn_total_tokens or max_item_tokens >= warn_max_item_tokens:
                log.warning(msg, *args)
            else:
                log.info(msg, *args)

        recent = con.execute(
            f"""
            SELECT created_at, source_type, source_name, ok, status_code, duration_ms, item_count, total_chars, est_tokens, max_item_chars, max_item_tokens, url, error
            FROM fetch_attempts
            WHERE {cond}
            ORDER BY created_at DESC
            LIMIT ?
            """.strip(),
            tuple(params + [limit2]),
        ).fetchall()

        for r in recent:
            ts_iso = dt.datetime.fromtimestamp(int(r[0])).isoformat() if r[0] else ""
            log.info(
                "attempt: ts=%s type=%s name=%s ok=%s status=%s ms=%s items=%s total_chars=%s est_tokens=%s max_item_chars=%s max_item_tokens=%s url=%s err=%s",
                ts_iso,
                r[1],
                r[2],
                "Y" if r[3] else "N",
                "" if r[4] is None else r[4],
                r[5],
                r[6],
                r[7] or 0,
                r[8] or 0,
                r[9] or 0,
                r[10] or 0,
                r[11],
                (r[12] or "")[:200],
            )

    out_cfg = (cfg or {}).get("output") or {}
    fetch_archives_dir = Path(out_cfg.get("fetch_archives_dir") or "./out/fetch_archives")
    if not fetch_archives_dir.exists():
        return

    files = sorted(
        [p for p in fetch_archives_dir.rglob("*_filtered_*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return

    log.info("filtered archives found=%d dir=%s", len(files), str(fetch_archives_dir))
    shown = 0
    for p in files:
        if shown >= limit2:
            break
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("filtered archive read failed: %s err=%s", str(p), str(e))
            continue

        if not isinstance(payload, dict):
            continue

        raw_count = payload.get("raw_items_count")
        if raw_count is None:
            raw_count = payload.get("raw_count")
        filtered_count = payload.get("filtered_items_count")
        if filtered_count is None:
            items2 = payload.get("items")
            filtered_count = len(items2) if isinstance(items2, list) else None

        ep_date = (payload.get("episode_date") or "").strip()
        dropped = None
        if isinstance(raw_count, int) and isinstance(filtered_count, int):
            dropped = raw_count - filtered_count

        msg = "filter: date=%s file=%s raw=%s filtered=%s dropped=%s"
        args = (ep_date, p.name, raw_count, filtered_count, dropped)
        if isinstance(raw_count, int) and raw_count > 0 and isinstance(filtered_count, int) and filtered_count == 0:
            log.warning(msg, *args)
        else:
            log.info(msg, *args)
        shown += 1


def step_list_items(
    store: Store, items_source: str | None, items_limit: int, items_show_content: bool, items_text_limit: int
) -> None:
    log = logging.getLogger("step.list_items")

    source = (items_source or "").strip() or None
    limit = max(1, int(items_limit or 10))
    text_limit = max(0, int(items_text_limit or 0))

    conditions: list[str] = []
    params: list[object] = []
    if source:
        conditions.append("source = ?")
        params.append(source)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with store._connect() as con:  # noqa: SLF001
        total = con.execute(f"SELECT COUNT(*) FROM items{where}", tuple(params)).fetchone()[0]
        cond2 = list(conditions)
        params2 = list(params)
        cond2.append("used_episode_id IS NULL")
        where2 = " WHERE " + " AND ".join(cond2)
        unused = con.execute(f"SELECT COUNT(*) FROM items{where2}", tuple(params2)).fetchone()[0]

        log.info("items total=%d unused=%d source_filter=%s", total, unused, source or "<all>")

        rows = con.execute(
            f"SELECT source, COUNT(*) AS cnt FROM items{where} GROUP BY source ORDER BY cnt DESC",
            tuple(params),
        ).fetchall()
        for r in rows:
            log.info("items by source: %s=%d", r[0], r[1])

        latest = con.execute(
            f"""
            SELECT id, title, summary, content, source, published_at, url, used_episode_id
            FROM items{where}
            ORDER BY COALESCE(published_at, '') DESC, updated_at DESC
            LIMIT ?
            """.strip(),
            tuple(params + [limit]),
        ).fetchall()

        for r in latest:
            log.info(
                "item: source=%s used=%s published_at=%s title=%s url=%s",
                r[4],
                "Y" if r[7] else "N",
                r[5] or "",
                r[1] or "",
                r[6] or "",
            )

            if items_show_content:
                summary = (r[2] or "").strip()
                content = (r[3] or "").strip()
                if text_limit > 0:
                    if len(summary) > text_limit:
                        summary = summary[:text_limit]
                    if len(content) > text_limit:
                        content = content[:text_limit]
                if summary:
                    log.info("item summary: %s", summary)
                if content:
                    log.info("item content: %s", content)


def step_list_newsnow_sources(cfg: dict, timeout_s: int, base_url: str | None, limit: int) -> None:
    log = logging.getLogger("step.list_newsnow_sources")

    sources_cfg = (cfg.get("sources") or {}).get("newsnow") or []
    base_urls: list[str] = []
    for s in sources_cfg:
        if not isinstance(s, dict):
            continue
        u = ((s.get("base_url") or "").strip() or os.environ.get("NEWSNOW_BASE_URL", "").strip()).strip()
        if u:
            base_urls.append(u)
    if base_url and base_url.strip():
        base_urls = [base_url.strip()]
    if not base_urls:
        base_urls = ["https://newsnow.busiyi.world"]

    catalog = fetch_newsnow_sources_catalog(timeout_seconds=timeout_s)
    ids = sorted([k for k in catalog.keys() if k])
    limit2 = max(1, int(limit or 100))

    log.info("newsnow base_urls=%s", ",".join(base_urls))
    log.info("newsnow catalog candidates=%d", len(ids))

    shown = 0
    ok_total = 0
    for sid in ids:
        if shown >= limit2:
            break

        meta = catalog.get(sid) or {}
        name = meta.get("name") if isinstance(meta, dict) else None
        title = meta.get("title") if isinstance(meta, dict) else None
        column = meta.get("column") if isinstance(meta, dict) else None
        redirect = meta.get("redirect") if isinstance(meta, dict) else None

        ok_any = False
        status_any: int | None = None
        err_any: str | None = None
        for bu in base_urls:
            ok, sc, err = probe_newsnow_source_id(base_url=bu, source_id=sid, timeout_seconds=timeout_s)
            status_any = sc
            err_any = err
            if ok:
                ok_any = True
                break

        if ok_any:
            ok_total += 1

        log.info(
            "source: id=%s ok=%s status=%s name=%s title=%s column=%s redirect=%s",
            sid,
            "Y" if ok_any else "N",
            "" if status_any is None else status_any,
            name or "",
            title or "",
            column or "",
            redirect or "",
        )
        if err_any:
            log.info("source err: id=%s err=%s", sid, (err_any or "")[:200])

        shown += 1

    log.info("newsnow sources shown=%d ok=%d", shown, ok_total)


def step_script(store: Store, cfg: dict, episode_id: str, timeout_s: int) -> None:
    log = logging.getLogger("step.script")

    ep = store.get_episode(episode_id)
    if ep["status"] in {"scripted", "tts_done", "rendered", "published"}:
        log.info("episode already scripted or later; skip")
        return

    pick_items = int((cfg.get("pipeline") or {}).get("pick_items") or 5)
    channel = cfg.get("channel") or {}

    items = store.pick_items_for_episode(episode_id=episode_id, limit=pick_items)
    if not items:
        raise RuntimeError("no items available to script")

    input_items = [
        ScriptInputItem(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            content=row["content"],
            url=row["url"],
            published_at=row["published_at"],
        )
        for row in items
    ]

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    if not base_url or not api_key:
        raise RuntimeError("DeepSeek not configured: set DEEPSEEK_BASE_URL and DEEPSEEK_API_KEY")

    temperature = float((cfg.get("deepseek") or {}).get("temperature") or 0.7)

    client = DeepSeekClient(base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout_s)
    out: ScriptOutput = client.generate(channel=channel, items=input_items, temperature=temperature)

    store.set_episode_script(
        episode_id=episode_id,
        title=out.title,
        ssml=out.ssml,
        shownotes=out.shownotes,
        tags=out.tags,
        script_json=json.dumps(out.model_dump(), ensure_ascii=False),
    )

    store.mark_items_used([row["id"] for row in items], episode_id=episode_id)
    store.set_episode_status(episode_id, "scripted")

    log.info("scripted: title=%s tags=%s", out.title, ",".join(out.tags))


def step_tts(store: Store, cfg: dict, episode_id: str, timeout_s: int) -> None:
    log = logging.getLogger("step.tts")

    ep = store.get_episode(episode_id)
    if ep["status"] in {"tts_done", "rendered", "published"}:
        if ep.get("tts_audio_path") and Path(ep["tts_audio_path"]).exists():
            log.info("episode already tts_done or later; skip")
            return
        raise RuntimeError("episode marked tts_done but tts_audio_path missing or file not found")

    if ep.get("tts_audio_path") and Path(ep["tts_audio_path"]).exists():
        store.set_episode_status(episode_id, "tts_done")
        log.info("found existing tts audio; reconciled status to tts_done")
        return

    if ep["status"] != "scripted":
        raise RuntimeError(f"tts requires scripted episode; current={ep['status']}")

    from src.tts.doubao import DoubaoTTSClient

    out_dir = Path((cfg.get("output") or {}).get("out_dir") or "./out")
    episodes_dir = Path((cfg.get("output") or {}).get("episodes_dir") or "./out/episodes")
    out_dir.mkdir(parents=True, exist_ok=True)
    episodes_dir.mkdir(parents=True, exist_ok=True)

    voice = ((cfg.get("tts") or {}).get("voice") or "").strip()

    client = DoubaoTTSClient(timeout_seconds=timeout_s)
    task_id = client.submit(ssml=ep["ssml"], voice=voice)

    audio_bytes = client.poll(task_id=task_id)
    tts_path = episodes_dir / f"{ep['episode_date']}.tts.mp3"
    tts_path.write_bytes(audio_bytes)

    store.set_episode_tts(episode_id=episode_id, task_id=task_id, tts_audio_path=str(tts_path))
    store.set_episode_status(episode_id, "tts_done")

    log.info("tts done: %s", tts_path)


def step_render(store: Store, cfg: dict, episode_id: str, timeout_s: int) -> None:
    log = logging.getLogger("step.render")

    ep = store.get_episode(episode_id)
    if ep["status"] in {"rendered", "published"}:
        if ep.get("rendered_audio_path") and Path(ep["rendered_audio_path"]).exists():
            log.info("episode already rendered or later; skip")
            return
        raise RuntimeError("episode marked rendered but rendered_audio_path missing or file not found")

    if ep.get("rendered_audio_path") and Path(ep["rendered_audio_path"]).exists():
        store.set_episode_status(episode_id, "rendered")
        log.info("found existing rendered audio; reconciled status to rendered")
        return

    if ep["status"] != "tts_done":
        raise RuntimeError(f"render requires tts_done episode; current={ep['status']}")

    audio_cfg = cfg.get("audio") or {}
    assets_dir = Path(audio_cfg.get("assets_dir") or "./assets")
    intro = assets_dir / (audio_cfg.get("intro") or "intro.mp3")
    outro = assets_dir / (audio_cfg.get("outro") or "outro.mp3")
    bgm = assets_dir / (audio_cfg.get("bgm") or "bgm.mp3")
    bgm_volume = float(audio_cfg.get("bgm_volume") or 0.18)

    episodes_dir = Path((cfg.get("output") or {}).get("episodes_dir") or "./out/episodes")
    episodes_dir.mkdir(parents=True, exist_ok=True)

    rendered_path = episodes_dir / f"{ep['episode_date']}.final.mp3"

    render_episode_audio(
        intro_path=intro,
        main_path=Path(ep["tts_audio_path"]),
        outro_path=outro,
        bgm_path=bgm,
        bgm_volume=bgm_volume,
        out_path=rendered_path,
        timeout_seconds=timeout_s,
    )

    store.set_episode_rendered(episode_id=episode_id, rendered_audio_path=str(rendered_path))
    store.set_episode_status(episode_id, "rendered")

    log.info("rendered: %s", rendered_path)


def step_publish(store: Store, cfg: dict, episode_id: str) -> None:
    log = logging.getLogger("step.publish")

    ep = store.get_episode(episode_id)
    if ep["status"] == "published":
        if ep.get("published_path") and Path(ep["published_path"]).exists():
            log.info("episode already published; skip")
            return
        raise RuntimeError("episode marked published but published_path missing or file not found")

    if ep.get("published_path") and Path(ep["published_path"]).exists():
        store.set_episode_status(episode_id, "published")
        log.info("found existing published audio; reconciled status to published")
        return

    if ep["status"] != "rendered":
        raise RuntimeError(f"publish requires rendered episode; current={ep['status']}")

    episodes_dir = Path((cfg.get("output") or {}).get("episodes_dir") or "./out/episodes")
    episodes_dir.mkdir(parents=True, exist_ok=True)

    tags_list = [t for t in (ep["tags"] or "").split(",") if t] if ep.get("tags") else []

    published_path = publish_local(
        rendered_audio_path=Path(ep["rendered_audio_path"]),
        episodes_dir=episodes_dir,
        episode_date=ep["episode_date"],
        title=ep["title"] or "",
        shownotes=ep["shownotes"] or "",
        tags=tags_list,
    )

    store.set_episode_published(episode_id=episode_id, published_path=str(published_path))
    store.set_episode_status(episode_id, "published")

    log.info("published: %s", published_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="./config/settings.yaml")
    parser.add_argument("--date", default=None)
    parser.add_argument(
        "--step",
        default="all",
        choices=[
            "all",
            "fetch",
            "script",
            "tts",
            "render",
            "publish",
            "list-items",
            "list-fetch-health",
            "list-fetch-health-trend",
            "list-newsnow-sources",
        ],
    )
    parser.add_argument("--force-fetch", action="store_true")
    parser.add_argument("--items-limit", type=int, default=10)
    parser.add_argument("--items-source", default=None)
    parser.add_argument("--items-show-content", action="store_true")
    parser.add_argument("--items-text-limit", type=int, default=200)
    parser.add_argument("--health-days", type=int, default=7)
    parser.add_argument("--health-limit", type=int, default=50)
    parser.add_argument("--health-only-failed", action="store_true")
    parser.add_argument("--newsnow-base-url", default=None)
    parser.add_argument("--newsnow-limit", type=int, default=80)
    args = parser.parse_args()

    load_dotenv(override=False)

    cfg = _load_yaml(Path(args.config))
    episode_date = args.date or _today_str()

    out_cfg = cfg.get("output") or {}
    logs_dir = Path(out_cfg.get("logs_dir") or "./out/logs")
    _setup_logging(logs_dir, episode_date)

    timeout_s = int(os.environ.get("HTTP_TIMEOUT_SECONDS", "20"))

    db_path = os.environ.get("PODCAST_DB_PATH", "./out/podcast.sqlite")
    store = Store(db_path=db_path)
    store.init_schema()

    channel_id = (cfg.get("channel") or {}).get("id") or "default"
    episode_id = store.get_or_create_episode(channel_id=channel_id, episode_date=episode_date)

    log = logging.getLogger("run")
    log.info("episode_id=%s date=%s step=%s", episode_id, episode_date, args.step)

    try:
        if args.step in {"all", "fetch"}:
            step_fetch(
                store=store,
                cfg=cfg,
                episode_id=episode_id,
                timeout_s=timeout_s,
                force_fetch=bool(args.force_fetch),
            )
        if args.step == "list-items":
            step_list_items(
                store=store,
                items_source=args.items_source,
                items_limit=args.items_limit,
                items_show_content=bool(args.items_show_content),
                items_text_limit=int(args.items_text_limit),
            )
        if args.step == "list-fetch-health":
            step_list_fetch_health(
                store=store,
                cfg=cfg,
                days=int(args.health_days),
                limit=int(args.health_limit),
                only_failed=bool(args.health_only_failed),
            )
        if args.step == "list-fetch-health-trend":
            step_list_fetch_health_trend(
                store=store,
                days=int(args.health_days),
                limit=int(args.health_limit),
            )
        if args.step == "list-newsnow-sources":
            step_list_newsnow_sources(
                cfg=cfg,
                timeout_s=timeout_s,
                base_url=args.newsnow_base_url,
                limit=int(args.newsnow_limit),
            )
        if args.step in {"all", "script"}:
            step_script(store=store, cfg=cfg, episode_id=episode_id, timeout_s=timeout_s)
        if args.step in {"all", "tts"}:
            step_tts(store=store, cfg=cfg, episode_id=episode_id, timeout_s=timeout_s)
        if args.step in {"all", "render"}:
            step_render(store, cfg, episode_id, timeout_s)
        if args.step in {"all", "publish"}:
            step_publish(store, cfg, episode_id)
    except Exception as e:
        log.error("error: %s", e)
        return 1

    log.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
