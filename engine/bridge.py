# coding=utf-8
"""
TrendRadar Bridge — 桥接层

职责：
1. 隔离导入 TrendRadar 的 DataFetcher（自动处理 sys.path）
2. 读取 TrendRadar 自身的 config.yaml 获取平台列表
3. 调用 DataFetcher.crawl_websites() 拉取热榜原始数据
4. 将原始数据转换为 auto-podcast fetch 节点的标准格式

本模块是 TrendRadar 与 auto-podcast 之间的 **唯一接触点**。
TrendRadar 代码库保持完全隔离，不做任何修改。
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


def _log(msg: str):
    """日志输出到 stderr，避免污染 fetch 节点的 JSON stdout。"""
    print(msg, file=sys.stderr)


ENGINE_DIR = Path(__file__).resolve().parent
TRENDRADAR_ROOT = ENGINE_DIR / "trendradar"
LOCK_FILE = ENGINE_DIR / "trendradar.lock.json"
_FETCHER_PATH = TRENDRADAR_ROOT / "trendradar" / "crawler" / "fetcher.py"


def get_data_fetcher():
    """
    直接加载 TrendRadar 的 fetcher.py，绕过 trendradar 包的 __init__.py。

    这样做是因为 trendradar.__init__ 会触发完整的依赖链
    (litellm, boto3, feedparser 等)，而我们只需要 DataFetcher 类，
    它仅依赖 requests + json + random + time（都是已有依赖）。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_trendradar_fetcher", str(_FETCHER_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DataFetcher


def load_trendradar_platforms() -> List[Dict[str, str]]:
    """
    从 TrendRadar 的 config.yaml 读取平台列表。

    Returns:
        [{"id": "toutiao", "name": "今日头条"}, ...]
    """
    import yaml

    config_path = TRENDRADAR_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        _log(f"[bridge] config.yaml not found: {config_path}")
        return []

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    platforms_cfg = cfg.get("platforms", {})
    if not platforms_cfg.get("enabled", True):
        return []

    sources = platforms_cfg.get("sources", [])
    return [
        {
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "enabled": s.get("enabled", True),
            "expected_domain": s.get("expected_domain", ""),
        }
        for s in sources
    ]


def _ensure_trendradar_path():
    root = str(TRENDRADAR_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log(f"[bridge] Failed to read json {path}: {exc}")
    return default


def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    try:
        repaired = text.encode("latin1").decode("gbk")
        if repaired and repaired != text:
            return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_version(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Version:\s*([0-9.]+)", text, re.IGNORECASE)
    return match.group(1) if match else None


def _parse_version_tuple(value: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", value or "0")[:3]) or (0,)


def _python_satisfies(requirement: str, version: str) -> bool:
    if not requirement or not version:
        return True
    match = re.match(r">=\s*([0-9.]+)", requirement)
    if not match:
        return True
    return _parse_version_tuple(version) >= _parse_version_tuple(match.group(1))


def _read_local_version() -> Optional[str]:
    version_file = TRENDRADAR_ROOT / "version"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8", errors="ignore").strip()
    pyproject = TRENDRADAR_ROOT / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8", errors="ignore"))
        if match:
            return match.group(1)
    return None


def _read_pyproject_requirement(path: Path) -> str:
    if not path.exists():
        return ""
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else ""


def _get_runtime_requirement() -> str:
    lock = get_lock_info()
    return lock.get("python") or _read_pyproject_requirement(TRENDRADAR_ROOT / "pyproject.toml")


def _missing_runtime_modules() -> List[str]:
    # DataFetcher only needs requests and works in the thin adapter. These are
    # the modules required by the fuller TrendRadar 6.10 RSS/AI/report chain.
    required = {
        "feedparser": "feedparser",
        "litellm": "litellm",
        "json-repair": "json_repair",
        "boto3": "boto3",
        "tenacity": "tenacity",
        "fastmcp": "fastmcp",
        "websockets": "websockets",
    }
    missing = []
    for package_name, module_name in required.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def _runtime_health() -> Dict[str, Any]:
    requirement = _get_runtime_requirement()
    python_version = ".".join(map(str, sys.version_info[:3]))
    python_compatible = _python_satisfies(requirement, python_version)
    missing_modules = _missing_runtime_modules()
    blocker_parts = []
    if not python_compatible:
        blocker_parts.append(f"TrendRadar {_read_local_version() or ''} 要求 Python {requirement}，当前为 {python_version}")
    if missing_modules:
        blocker_parts.append(f"缺少依赖：{', '.join(missing_modules)}")
    return {
        "pythonRequirement": requirement,
        "pythonVersion": python_version,
        "pythonExecutable": sys.executable,
        "pythonCompatible": python_compatible,
        "missingDependencies": missing_modules,
        "fullRuntimeAvailable": python_compatible and not missing_modules,
        "runtimeBlocked": bool(blocker_parts),
        "runtimeBlocker": "；".join(blocker_parts),
        "adapterAvailable": TRENDRADAR_ROOT.exists() and _FETCHER_PATH.exists(),
    }


def _fetch_text(url: str, timeout: int = 15) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _get_user_paths(user_data_dir: Optional[str] = None) -> Dict[str, Path]:
    base = Path(user_data_dir or os.environ.get("AUTO_PODCAST_USER_DATA") or (ENGINE_DIR / "trendradar_data"))
    root = base / "trendradar"
    return {
        "root": root,
        "config": root / "config.json",
        "latest": root / "latest.json",
        "status": root / "status.json",
        "reports": root / "reports",
        "backup": root / "backups",
    }


def get_lock_info() -> Dict[str, Any]:
    return _read_json(LOCK_FILE, {})


def get_config_view(user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    source_cfg = _load_yaml(TRENDRADAR_ROOT / "config" / "config.yaml")
    user_cfg = _read_json(_get_user_paths(user_data_dir)["config"], {})

    platforms_cfg = source_cfg.get("platforms", {})
    rss_cfg = source_cfg.get("rss", {})
    advanced = source_cfg.get("advanced", {})
    ai_cfg = source_cfg.get("ai", {})
    filter_cfg = source_cfg.get("filter", {})

    platform_sources = [
        p for p in platforms_cfg.get("sources", []) if p.get("enabled", True)
    ]
    rss_sources = [
        f for f in rss_cfg.get("feeds", []) if f.get("enabled", True)
    ]

    view = {
        "platforms_enabled": platforms_cfg.get("enabled", True),
        "rss_enabled": rss_cfg.get("enabled", True),
        "enabled_platforms": [p.get("id") for p in platform_sources if p.get("id")],
        "enabled_rss_feeds": [f.get("id") for f in rss_sources if f.get("id")],
        "max_items_per_source": 30,
        "freshness_days": rss_cfg.get("freshness_filter", {}).get("max_age_days", 3),
        "filter_method": filter_cfg.get("method", "keyword"),
        "ai_available": bool(ai_cfg.get("api_key") or os.environ.get("AI_API_KEY")),
        "ai_model": ai_cfg.get("model", ""),
        "api_url": platforms_cfg.get("api_url", ""),
        "proxy_enabled": advanced.get("crawler", {}).get("use_proxy", False),
        "proxy_url": advanced.get("crawler", {}).get("default_proxy", ""),
        "schedule_preset": source_cfg.get("schedule", {}).get("preset", "morning_evening"),
        "report_mode": source_cfg.get("report", {}).get("mode", "current"),
        "raw": user_cfg.get("raw", {}),
    }
    view.update({k: v for k, v in user_cfg.items() if k != "raw"})
    if view["filter_method"] == "ai" and not view["ai_available"]:
        view["filter_method"] = "keyword"
        view["ai_disabled_reason"] = "未配置 AI_API_KEY，已回退到关键词筛选"
    return view


def save_config_view(config: Dict[str, Any], user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    paths = _get_user_paths(user_data_dir)
    current = get_config_view(user_data_dir)
    next_config = {**current, **(config or {})}
    if next_config.get("filter_method") == "ai" and not next_config.get("ai_available"):
        raise ValueError("AI 筛选需要先配置 TrendRadar AI API Key")
    _write_json(paths["config"], next_config)
    return next_config


def list_sources(user_data_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    cfg = get_config_view(user_data_dir)
    source_cfg = _load_yaml(TRENDRADAR_ROOT / "config" / "config.yaml")
    platforms = source_cfg.get("platforms", {}).get("sources", [])
    rss_feeds = source_cfg.get("rss", {}).get("feeds", [])
    enabled_platforms = set(cfg.get("enabled_platforms", []))
    enabled_rss = set(cfg.get("enabled_rss_feeds", []))
    sources: List[Dict[str, Any]] = []
    for p in platforms:
        pid = p.get("id")
        if not pid:
            continue
        sources.append({
            "id": pid,
            "name": _normalize_text(p.get("name", pid)),
            "kind": "platform",
            "enabled": pid in enabled_platforms,
            "description": _normalize_text(p.get("expected_domain", "")),
        })
    for feed in rss_feeds:
        fid = feed.get("id")
        if not fid:
            continue
        sources.append({
            "id": fid,
            "name": _normalize_text(feed.get("name", fid)),
            "kind": "rss",
            "enabled": fid in enabled_rss,
            "url": feed.get("url", ""),
        })
    return sources


def _make_item_id(kind: str, source_id: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{kind}|{source_id}|{title}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"tr_{kind}_{source_id}_{digest}"


def _normalize_platform_results(
    results: Dict[str, Dict],
    id_to_name: Dict[str, str],
    max_items_per_source: int,
) -> List[Dict[str, Any]]:
    now_iso = datetime.now(timezone.utc).isoformat()
    items: List[Dict[str, Any]] = []
    for platform_id, titles_data in results.items():
        platform_name = _normalize_text(id_to_name.get(platform_id, platform_id))
        for idx, (title, title_info) in enumerate((titles_data or {}).items(), 1):
            if idx > max_items_per_source:
                break
            title_text = _normalize_text(title)
            url = str(title_info.get("url") or title_info.get("mobileUrl") or "")
            ranks = title_info.get("ranks", [])
            rank = ranks[0] if ranks else idx
            item_id = _make_item_id("platform", platform_id, str(title), url)
            items.append({
                "trendradar_id": item_id,
                "title": title_text,
                "content": f"[{platform_name} #{rank}] {title_text}",
                "url": url,
                "published": now_iso,
                "source": f"trendradar_{platform_id}",
                "type": "hotlist",
                "source_kind": "platform",
                "source_id": platform_id,
                "source_name": platform_name,
                "platform_id": platform_id,
                "platform_name": platform_name,
                "rank": rank,
                "score": max(0, 101 - int(rank)),
                "first_seen": now_iso,
                "last_seen": now_iso,
                "matched_reason": f"{platform_name} 热榜第 {rank} 位",
            })
    return items


def _fetch_rss_items(config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    enabled_feeds = set(config.get("enabled_rss_feeds") or [])
    if not enabled_feeds or not config.get("rss_enabled", True):
        return [], []
    try:
        _ensure_trendradar_path()
        from trendradar.crawler.rss.fetcher import RSSFetcher
    except Exception as exc:
        _log(f"[bridge] RSSFetcher unavailable: {exc}")
        return [], ["rss"]

    source_cfg = _load_yaml(TRENDRADAR_ROOT / "config" / "config.yaml")
    rss_cfg = source_cfg.get("rss", {})
    advanced_rss = source_cfg.get("advanced", {}).get("rss", {})
    feeds = []
    for feed in rss_cfg.get("feeds", []):
        if feed.get("id") in enabled_feeds:
            feeds.append({**feed, "enabled": True, "max_items": config.get("max_items_per_source", 30)})
    if not feeds:
        return [], []
    fetcher_cfg = {
        **rss_cfg,
        **advanced_rss,
        "feeds": feeds,
        "freshness_filter": {"enabled": True, "max_age_days": config.get("freshness_days", 3)},
    }
    try:
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        try:
            data = RSSFetcher.from_config(fetcher_cfg).fetch_all()
        finally:
            sys.stdout = old_stdout
    except Exception as exc:
        _log(f"[bridge] RSS fetch failed: {exc}")
        return [], [f.get("id", "rss") for f in feeds]

    now_iso = datetime.now(timezone.utc).isoformat()
    items: List[Dict[str, Any]] = []
    for feed_id, feed_items in data.items.items():
        feed_name = _normalize_text(data.id_to_name.get(feed_id, feed_id))
        for idx, rss_item in enumerate(feed_items[: int(config.get("max_items_per_source", 30))], 1):
            title = _normalize_text(getattr(rss_item, "title", ""))
            url = getattr(rss_item, "url", "")
            published = getattr(rss_item, "published_at", "") or now_iso
            item_id = _make_item_id("rss", feed_id, title, url)
            summary = _normalize_text(getattr(rss_item, "summary", "") or title)
            items.append({
                "trendradar_id": item_id,
                "title": title,
                "content": summary,
                "url": url,
                "published": published,
                "source": f"trendradar_rss_{feed_id}",
                "type": "rss",
                "source_kind": "rss",
                "source_id": feed_id,
                "source_name": feed_name,
                "rank": idx,
                "score": max(0, 80 - idx),
                "first_seen": published,
                "last_seen": now_iso,
                "matched_reason": f"{feed_name} RSS",
            })
    return items, list(data.failed_ids or [])


def _apply_light_filters(items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    # TrendRadar owns the data source; this adapter only applies UI-facing source and count limits.
    if config.get("filter_method") == "ai" and not config.get("ai_available"):
        raise ValueError("AI 筛选需要先配置 TrendRadar AI API Key")
    return sorted(
        items,
        key=lambda item: (
            -(item.get("score") or 0),
            item.get("rank") or 9999,
            item.get("source_name") or "",
        ),
    )


def run_once(config_override: Optional[Dict[str, Any]] = None, user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    config = get_config_view(user_data_dir)
    config.update(config_override or {})
    if config.get("filter_method") == "ai" and not config.get("ai_available"):
        raise ValueError("AI 筛选需要先配置 TrendRadar AI API Key")

    platform_items: List[Dict[str, Any]] = []
    failed_sources: List[str] = []
    if config.get("platforms_enabled", True) and config.get("enabled_platforms"):
        results, id_to_name, failed_ids = fetch_trending(
            platform_ids=config.get("enabled_platforms"),
            proxy_url=config.get("proxy_url") if config.get("proxy_enabled") else None,
            api_url=config.get("api_url") or None,
            request_interval=100,
        )
        platform_items = _normalize_platform_results(
            results,
            id_to_name,
            int(config.get("max_items_per_source", 30) or 30),
        )
        failed_sources.extend(failed_ids or [])

    rss_items, rss_failed = _fetch_rss_items(config)
    failed_sources.extend(rss_failed)
    items = _apply_light_filters(platform_items + rss_items, config)
    generated_at = datetime.now(timezone.utc).isoformat()
    topics = get_topics_from_items(items)
    meta = {
        "generated_at": generated_at,
        "failed_sources": failed_sources,
        "platform_count": len(set(i.get("source_id") for i in platform_items)),
        "rss_count": len(set(i.get("source_id") for i in rss_items)),
        "item_count": len(items),
        "topics": topics,
        "config": {k: config.get(k) for k in [
            "filter_method", "max_items_per_source", "freshness_days",
            "enabled_platforms", "enabled_rss_feeds",
        ]},
    }
    result = {"success": True, "items": items, "fetch_contents": items, "meta": meta}
    paths = _get_user_paths(user_data_dir)
    _write_json(paths["latest"], result)
    _write_json(paths["status"], {
        "status": "idle",
        "updated_at": generated_at,
        "latestRunAt": generated_at,
        "latestItemCount": len(items),
        "lastError": None,
    })
    return result


def get_latest(user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    return _read_json(_get_user_paths(user_data_dir)["latest"], {"success": True, "items": [], "fetch_contents": [], "meta": {}})


def get_topics_from_items(items: List[Dict[str, Any]], top_n: int = 12) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for item in items:
        name = _normalize_text(item.get("source_name") or item.get("source") or "未知来源")
        counts[name] = counts.get(name, 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:top_n]
    ]


def get_topics(user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    latest = get_latest(user_data_dir)
    return {"success": True, "topics": get_topics_from_items(latest.get("items", []))}


def get_status(user_data_dir: Optional[str] = None) -> Dict[str, Any]:
    lock = get_lock_info()
    paths = _get_user_paths(user_data_dir)
    status = _read_json(paths["status"], {})
    runtime = _runtime_health()
    return {
        "available": TRENDRADAR_ROOT.exists(),
        "adapterAvailable": runtime.get("adapterAvailable", False),
        "fullRuntimeAvailable": runtime.get("fullRuntimeAvailable", False),
        "runtimeBlocked": runtime.get("runtimeBlocked", False),
        "runtimeBlocker": runtime.get("runtimeBlocker", ""),
        "pythonRequirement": runtime.get("pythonRequirement", ""),
        "pythonCompatible": runtime.get("pythonCompatible", True),
        "missingDependencies": runtime.get("missingDependencies", []),
        "processRunning": False,
        "status": status.get("status", "ready" if TRENDRADAR_ROOT.exists() else "missing"),
        "localVersion": _read_local_version(),
        "lockedVersion": lock.get("version"),
        "lockedCommit": lock.get("commit"),
        "pythonVersion": runtime.get("pythonVersion"),
        "pythonExecutable": runtime.get("pythonExecutable"),
        "userDataDir": str(paths["root"]),
        "latestRunAt": status.get("latestRunAt"),
        "latestItemCount": status.get("latestItemCount"),
        "lastError": status.get("lastError"),
    }


def check_update() -> Dict[str, Any]:
    lock = get_lock_info()
    local_version = _read_local_version()
    local_commit = ""
    try:
        local_commit = subprocess.check_output(
            ["git", "-C", str(TRENDRADAR_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    try:
        remote_version = _fetch_text("https://raw.githubusercontent.com/sansan0/TrendRadar/master/version").strip()
        remote_configs_text = _fetch_text("https://raw.githubusercontent.com/sansan0/TrendRadar/master/version_configs")
        pyproject_text = _fetch_text("https://raw.githubusercontent.com/sansan0/TrendRadar/master/pyproject.toml")
        remote_req_match = re.search(r'requires-python\s*=\s*"([^"]+)"', pyproject_text)
        remote_requirement = remote_req_match.group(1) if remote_req_match else ""
        remote_configs = {}
        for line in remote_configs_text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                remote_configs[k.strip()] = v.strip()
        runtime = _runtime_health()
        python_version = runtime["pythonVersion"]
        blocked = not _python_satisfies(remote_requirement, python_version)
        blockers = []
        if blocked:
            blockers.append(f"TrendRadar {remote_version} 要求 Python {remote_requirement}，当前为 {python_version}")
        if runtime.get("missingDependencies"):
            blockers.append(f"当前 TrendRadar 完整运行时缺少依赖：{', '.join(runtime['missingDependencies'])}")
        return {
            "success": True,
            "localVersion": local_version,
            "remoteVersion": remote_version,
            "lockedVersion": lock.get("version"),
            "localCommit": local_commit,
            "lockedCommit": lock.get("commit"),
            "remoteConfigVersions": remote_configs,
            "pythonVersion": python_version,
            "pythonRequirement": runtime.get("pythonRequirement", ""),
            "pythonCompatible": runtime.get("pythonCompatible", True),
            "missingDependencies": runtime.get("missingDependencies", []),
            "fullRuntimeAvailable": runtime.get("fullRuntimeAvailable", False),
            "remotePythonRequirement": remote_requirement,
            "updateAvailable": bool(remote_version and local_version and remote_version != local_version),
            "blocked": bool(blockers),
            "blocker": "；".join(blockers),
        }
    except Exception as exc:
        return {
            "success": False,
            "localVersion": local_version,
            "lockedVersion": lock.get("version"),
            "localCommit": local_commit,
            "lockedCommit": lock.get("commit"),
            "updateAvailable": False,
            "blocked": False,
            "error": str(exc),
        }


def update_dependency(ref: str = "latest", install_deps: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    update = check_update()
    runtime = _runtime_health()
    if not runtime.get("pythonCompatible", True):
        return {**update, "success": False}
    if update.get("blocked") and not install_deps:
        return {**update, "success": False}
    if dry_run:
        return {**update, "dryRun": True}
    if not TRENDRADAR_ROOT.exists():
        return {"success": False, "error": "engine/trendradar 不存在，请先运行同步脚本"}
    status = subprocess.run(
        ["git", "-C", str(TRENDRADAR_ROOT), "status", "--porcelain"],
        text=True,
        capture_output=True,
    )
    if status.stdout.strip():
        backup_dir = _get_user_paths(None)["backup"] / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "dirty-status.txt").write_text(status.stdout, encoding="utf-8")
        return {"success": False, "error": f"TrendRadar 有本地改动，已记录到 {backup_dir}", "dirty": True}
    target = "origin/master" if ref == "latest" else ref
    subprocess.check_call(["git", "-C", str(TRENDRADAR_ROOT), "fetch", "origin"])
    subprocess.check_call(["git", "-C", str(TRENDRADAR_ROOT), "checkout", target])
    if install_deps:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(TRENDRADAR_ROOT)])
    return {**check_update(), "success": True}


def fetch_trending(
    platform_ids: Optional[List[str]] = None,
    proxy_url: Optional[str] = None,
    api_url: Optional[str] = None,
    request_interval: int = 100,
) -> Tuple[Dict[str, Dict], Dict[str, str], List[str]]:
    """
    使用 TrendRadar 的 DataFetcher 拉取热榜原始数据。

    TrendRadar 的 fetcher.py 内部有 print() 调用，
    这里临时将 stdout 重定向到 stderr，避免污染 fetch 节点的 JSON 输出。

    Args:
        platform_ids: 要拉取的平台 ID 列表。None 时使用 config.yaml 中的全部平台。
        proxy_url: 代理地址（可选）
        api_url: 自定义 API 地址（可选）
        request_interval: 请求间隔（毫秒）

    Returns:
        (results, id_to_name, failed_ids)
        - results:  {platform_id: {title: {"ranks": [...], "url": "", "mobileUrl": ""}}}
        - id_to_name: {platform_id: display_name}
        - failed_ids: 拉取失败的平台 ID 列表
    """
    DataFetcher = get_data_fetcher()
    fetcher = DataFetcher(proxy_url=proxy_url, api_url=api_url)

    # 构建 ids_list：[(id, name), ...]
    platforms = load_trendradar_platforms()
    platform_map = {p["id"]: p["name"] for p in platforms}

    if platform_ids is None:
        platform_ids = [p["id"] for p in platforms]

    ids_list = [(pid, platform_map.get(pid, pid)) for pid in platform_ids]

    # 临时重定向 stdout → stderr，因为 TrendRadar fetcher.py 内部有 print()
    # 而 fetch 节点通过 stdout 返回 JSON 给 Electron
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        results, id_to_name, failed_ids = fetcher.crawl_websites(
            ids_list=ids_list,
            request_interval=request_interval,
        )
    finally:
        sys.stdout = old_stdout

    return results, id_to_name, failed_ids


def fetch_trending_as_items(
    platform_ids: Optional[List[str]] = None,
    max_items_per_platform: int = 30,
    use_cache: bool = True,
    cache_max_age_seconds: int = 3600,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    拉取热榜并转换为 auto-podcast fetch 节点的标准格式。

    优先从 daemon 缓存读取（如果 daemon 正在运行且数据新鲜），
    缓存不可用时回退到实时 API 调用。

    Args:
        platform_ids: 要拉取的平台 ID 列表
        max_items_per_platform: 每个平台最多返回的条目数
        use_cache: 是否优先使用 daemon 缓存（默认 True）
        cache_max_age_seconds: 缓存最大有效期（秒，默认 1 小时）
        **kwargs: 传递给 fetch_trending 的其他参数

    Returns:
        标准格式的热榜条目列表
    """
    # 尝试从 daemon 缓存读取
    if use_cache:
        items = _try_read_daemon_cache(platform_ids, max_items_per_platform, cache_max_age_seconds)
        if items is not None:
            return items

    # 回退：实时 API 调用
    results, id_to_name, failed_ids = fetch_trending(
        platform_ids=platform_ids, **kwargs
    )

    return convert_raw_to_items(results, id_to_name, max_items_per_platform)


def convert_raw_to_items(
    results: Dict[str, Dict],
    id_to_name: Dict[str, str],
    max_items_per_platform: int = 30,
) -> List[Dict[str, Any]]:
    """
    将 TrendRadar 原始爬取结果转换为 fetch 节点标准格式。

    这是 bridge 和 daemon 共用的转换逻辑（DRY 提取）。
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    items: List[Dict[str, Any]] = []

    for platform_id, titles_data in results.items():
        platform_name = _normalize_text(id_to_name.get(platform_id, platform_id))
        rank = 0

        for title, title_info in titles_data.items():
            title_text = _normalize_text(title)
            rank += 1
            if rank > max_items_per_platform:
                break

            url = title_info.get("url", "") or title_info.get("mobileUrl", "")
            ranks = title_info.get("ranks", [])
            rank_str = f"#{ranks[0]}" if ranks else f"#{rank}"

            items.append({
                "title": title_text,
                "content": f"[{platform_name} {rank_str}] {title_text}",
                "url": str(url),
                "published": now_iso,
                "source": f"trendradar_{platform_id}",
                "type": "hotlist",
                "platform_id": platform_id,
                "platform_name": platform_name,
                "rank": ranks[0] if ranks else rank,
            })

    return items


DAEMON_DATA_DIR = ENGINE_DIR / "trendradar_data"
_DAEMON_LATEST_FILE = DAEMON_DATA_DIR / "latest.json"


def _try_read_daemon_cache(
    platform_ids: Optional[List[str]],
    max_items_per_platform: int,
    max_age_seconds: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    尝试从 daemon 的 latest.json 读取缓存数据。
    如果缓存不存在或过期，返回 None（调用方回退到实时爬取）。
    """
    if not _DAEMON_LATEST_FILE.exists():
        return None

    try:
        data = json.loads(_DAEMON_LATEST_FILE.read_text(encoding="utf-8"))

        crawled_at = data.get("crawled_at", "")
        if crawled_at:
            crawl_time = datetime.fromisoformat(crawled_at)
            age = (datetime.now(timezone.utc) - crawl_time).total_seconds()
            if age > max_age_seconds:
                _log(f"[bridge] Daemon cache expired ({age:.0f}s > {max_age_seconds}s), falling back to live fetch")
                return None

        raw_items = data.get("items", [])
        if not raw_items:
            return None

        # 过滤平台和条目数
        platform_ids_set = set(platform_ids) if platform_ids else None
        platform_counts: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []

        for item in raw_items:
            pid = item.get("platform_id", "")
            if platform_ids_set and pid not in platform_ids_set:
                continue
            count = platform_counts.get(pid, 0)
            if count >= max_items_per_platform:
                continue
            platform_counts[pid] = count + 1

            items.append({
                "title": item["title"],
                "content": item["content"],
                "url": item["url"],
                "published": item["published"],
                "source": item["source"],
                "type": item["type"],
            })

        _log(f"[bridge] Using daemon cache ({len(items)} items, crawled {crawled_at})")
        return items

    except Exception as e:
        _log(f"[bridge] Failed to read daemon cache: {e}")
        return None


def get_daemon_status() -> Dict[str, Any]:
    """获取 daemon 守护进程状态，供前端/Electron 查询。"""
    status_file = DAEMON_DATA_DIR / "status.json"
    if not status_file.exists():
        return {"status": "not_running"}
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unknown"}
