# coding=utf-8
"""
TrendRadar Daemon — 后台持续爬取守护进程

职责：
  定时调用 TrendRadar DataFetcher 拉取全网热榜，
  将结果写入 engine/trendradar_data/latest.json 供 bridge 读取。

启动方式（由 Electron main.js 自动管理）：
  python -m engine.daemon                   # 默认 30 分钟间隔
  python -m engine.daemon --interval 15     # 15 分钟间隔
  python -m engine.daemon --once            # 只跑一次（用于调试）

数据流：
  TrendRadar DataFetcher → latest.json → bridge.py → newsnow.py → fetch 节点
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.bridge import (
    get_data_fetcher,
    load_trendradar_platforms,
    convert_raw_to_items,
    get_daemon_status,
    DAEMON_DATA_DIR,
)

_LATEST_FILE = DAEMON_DATA_DIR / "latest.json"
_STATUS_FILE = DAEMON_DATA_DIR / "status.json"

_running = True


def _signal_handler(signum, frame):
    global _running
    print(f"\n[daemon] Received signal {signum}, shutting down gracefully...")
    _running = False


def _write_status(status: str, **extra):
    """写入守护进程状态文件。"""
    DAEMON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "status": status,
        "pid": os.getpid(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    _STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def crawl_once() -> dict:
    """执行一次完整爬取，返回结果摘要。"""
    DataFetcher = get_data_fetcher()
    fetcher = DataFetcher()

    platforms = load_trendradar_platforms()
    ids_list = [(p["id"], p["name"]) for p in platforms]

    print(f"[daemon] Crawling {len(ids_list)} platforms...")
    results, id_to_name, failed_ids = fetcher.crawl_websites(ids_list, request_interval=100)

    items = convert_raw_to_items(results, id_to_name)

    now_iso = datetime.now(timezone.utc).isoformat()
    output = {
        "crawled_at": now_iso,
        "platform_count": len(results),
        "item_count": len(items),
        "failed_ids": failed_ids,
        "platforms": {pid: pname for pid, pname in id_to_name.items()},
        "items": items,
    }

    DAEMON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _LATEST_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[daemon] Crawled {len(items)} items from {len(results)} platforms, "
          f"failed: {failed_ids or 'none'}")
    return output


def run_daemon(interval_min: int = 30, once: bool = False):
    """主守护循环。"""
    global _running

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print(f"[daemon] TrendRadar daemon starting (PID={os.getpid()}, interval={interval_min}min)")
    _write_status("starting", interval_min=interval_min)

    while _running:
        try:
            _write_status("crawling", interval_min=interval_min)
            result = crawl_once()
            _write_status(
                "idle",
                interval_min=interval_min,
                last_crawl_at=result["crawled_at"],
                last_item_count=result["item_count"],
                last_platform_count=result["platform_count"],
                last_failed_ids=result["failed_ids"],
            )
        except Exception as e:
            print(f"[daemon] Crawl error: {e}")
            _write_status("error", interval_min=interval_min, error=str(e))

        if once:
            print("[daemon] --once mode, exiting.")
            break

        # 等待下一次，每秒检查 _running 状态以便快速退出
        wait_seconds = interval_min * 60
        print(f"[daemon] Next crawl in {interval_min} minutes...")
        for _ in range(wait_seconds):
            if not _running:
                break
            time.sleep(1)

    _write_status("stopped", interval_min=interval_min)
    print("[daemon] Daemon stopped.")


def read_latest_items():
    """读取 daemon 最近一次爬取的数据。返回 (items, metadata) 或 (None, None)。"""
    if not _LATEST_FILE.exists():
        return None, None
    try:
        data = json.loads(_LATEST_FILE.read_text(encoding="utf-8"))
        return data.get("items", []), {
            "crawled_at": data.get("crawled_at"),
            "platform_count": data.get("platform_count"),
            "item_count": data.get("item_count"),
        }
    except Exception:
        return None, None


# read_daemon_status is provided by bridge.get_daemon_status() — use that instead

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrendRadar background crawler daemon")
    parser.add_argument("--interval", type=int, default=30, help="Crawl interval in minutes (default: 30)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    run_daemon(interval_min=args.interval, once=args.once)
