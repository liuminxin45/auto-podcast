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

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


def _log(msg: str):
    """日志输出到 stderr，避免污染 fetch 节点的 JSON stdout。"""
    print(msg, file=sys.stderr)


ENGINE_DIR = Path(__file__).resolve().parent
TRENDRADAR_ROOT = ENGINE_DIR / "trendradar"
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
    return [{"id": s["id"], "name": s.get("name", s["id"])} for s in sources]


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
        platform_name = id_to_name.get(platform_id, platform_id)
        rank = 0

        for title, title_info in titles_data.items():
            rank += 1
            if rank > max_items_per_platform:
                break

            url = title_info.get("url", "") or title_info.get("mobileUrl", "")
            ranks = title_info.get("ranks", [])
            rank_str = f"#{ranks[0]}" if ranks else f"#{rank}"

            items.append({
                "title": title,
                "content": f"[{platform_name} {rank_str}] {title}",
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
