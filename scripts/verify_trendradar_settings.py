#!/usr/bin/env python
# coding=utf-8
"""Offline regression checks for DiscoverPanel TrendRadar settings.

The checks intentionally avoid real network calls. They patch the TrendRadar
adapter fetch functions and verify that UI-facing config values reach the
bridge and change output, metadata, or fetch arguments.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import bridge


UI_CONFIG_KEYS = [
    "timezone",
    "show_version_update",
    "platforms_enabled",
    "rss_enabled",
    "enabled_platforms",
    "enabled_rss_feeds",
    "max_items_per_source",
    "freshness_days",
    "rss_freshness_enabled",
    "rss_request_interval",
    "rss_timeout",
    "rss_proxy_enabled",
    "rss_proxy_url",
    "crawler_request_interval",
    "filter_method",
    "filter_priority_sort_enabled",
    "ai_available",
    "ai_api_key_set",
    "ai_provider_source",
    "ai_model",
    "ai_api_base",
    "ai_timeout",
    "ai_temperature",
    "ai_max_tokens",
    "ai_num_retries",
    "ai_fallback_models",
    "ai_filter_batch_size",
    "ai_filter_batch_interval",
    "ai_filter_min_score",
    "ai_filter_reclassify_threshold",
    "ai_interests_file",
    "ai_filter_prompt_file",
    "ai_filter_extract_prompt_file",
    "ai_filter_update_tags_prompt_file",
    "api_url",
    "proxy_enabled",
    "proxy_url",
    "schedule_preset",
    "report_mode",
    "report_display_mode",
    "sort_by_position_first",
    "rank_threshold",
    "max_news_per_keyword",
    "display_standalone_enabled",
    "standalone_platforms",
    "standalone_rss_feeds",
    "standalone_max_items",
    "debug",
]


PLATFORM_RESULTS = {
    "source_a": {
        "AI alpha": {"ranks": [1], "url": "https://example.test/a1"},
        "Other noise": {"ranks": [2], "url": "https://example.test/a2"},
        "Cloud gamma": {"ranks": [3], "url": "https://example.test/a3"},
    },
    "source_b": {
        "Cloud beta": {"ranks": [1], "url": "https://example.test/b1"},
        "AI delta": {"ranks": [4], "url": "https://example.test/b2"},
    },
}


def install_fake_frequency_module() -> None:
    trendradar_mod = types.ModuleType("trendradar")
    trendradar_core_mod = types.ModuleType("trendradar.core")
    frequency_mod = types.ModuleType("trendradar.core.frequency")

    def _word_matches(rule: Any, title: str) -> bool:
        return str(rule).lower() in str(title).lower()

    frequency_mod._word_matches = _word_matches  # type: ignore[attr-defined]
    sys.modules["trendradar"] = trendradar_mod
    sys.modules["trendradar.core"] = trendradar_core_mod
    sys.modules["trendradar.core.frequency"] = frequency_mod


def install_fake_keyword_rules() -> None:
    bridge._load_keyword_rules = lambda: (  # type: ignore[assignment]
        [
            {"display_name": "AI", "normal": ["ai"], "max_count": 1},
            {"display_name": "Cloud", "normal": ["cloud"], "max_count": 0},
        ],
        [],
        [],
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_base_config() -> Dict[str, Any]:
    return {
        "timezone": "UTC",
        "show_version_update": False,
        "platforms_enabled": True,
        "rss_enabled": True,
        "enabled_platforms": ["source_a"],
        "enabled_rss_feeds": ["feed_a"],
        "max_items_per_source": 3,
        "freshness_days": 9,
        "rss_freshness_enabled": True,
        "rss_request_interval": 77,
        "rss_timeout": 11,
        "rss_proxy_enabled": True,
        "rss_proxy_url": "http://127.0.0.1:18080",
        "crawler_request_interval": 123,
        "filter_method": "keyword",
        "filter_priority_sort_enabled": True,
        "ai_available": False,
        "ai_api_key_set": False,
        "ai_provider_source": "none",
        "ai_model": "",
        "ai_api_base": "",
        "ai_timeout": 120,
        "ai_temperature": 1,
        "ai_max_tokens": 5000,
        "ai_num_retries": 1,
        "ai_fallback_models": [],
        "ai_filter_batch_size": 200,
        "ai_filter_batch_interval": 2,
        "ai_filter_min_score": 0.7,
        "ai_filter_reclassify_threshold": 0.6,
        "ai_interests_file": "ai_interests.txt",
        "ai_filter_prompt_file": "prompt.txt",
        "ai_filter_extract_prompt_file": "extract_prompt.txt",
        "ai_filter_update_tags_prompt_file": "update_tags_prompt.txt",
        "api_url": "https://newsnow.example.test/api",
        "proxy_enabled": True,
        "proxy_url": "http://127.0.0.1:10801",
        "schedule_preset": "manual",
        "report_mode": "current",
        "report_display_mode": "keyword",
        "sort_by_position_first": True,
        "rank_threshold": 1,
        "max_news_per_keyword": 1,
        "display_standalone_enabled": False,
        "standalone_platforms": [],
        "standalone_rss_feeds": [],
        "standalone_max_items": 5,
        "debug": True,
    }


def verify_meta_config(result: Dict[str, Any], expected: Dict[str, Any]) -> None:
    meta_config = result["meta"]["config"]
    missing = [key for key in UI_CONFIG_KEYS if key not in meta_config]
    assert_true(not missing, f"meta.config missing UI keys: {missing}")
    for key, value in expected.items():
        if key in UI_CONFIG_KEYS:
            assert_true(meta_config.get(key) == value, f"{key} not echoed in meta.config")


def main() -> int:
    install_fake_frequency_module()
    install_fake_keyword_rules()

    captured_fetches: List[Dict[str, Any]] = []
    captured_rss: List[Dict[str, Any]] = []

    def fake_fetch_trending(platform_ids=None, proxy_url=None, api_url=None, request_interval=0):
        captured_fetches.append({
            "platform_ids": list(platform_ids or []),
            "proxy_url": proxy_url,
            "api_url": api_url,
            "request_interval": request_interval,
        })
        selected = platform_ids or list(PLATFORM_RESULTS.keys())
        return (
            {pid: PLATFORM_RESULTS[pid] for pid in selected if pid in PLATFORM_RESULTS},
            {"source_a": "来源 A", "source_b": "来源 B"},
            [],
        )

    def fake_fetch_rss_items(config: Dict[str, Any]):
        captured_rss.append(dict(config))
        if not config.get("rss_enabled", True):
            return [], []
        items = []
        for feed_id in config.get("enabled_rss_feeds") or []:
            items.append({
                "trendradar_id": f"tr_rss_{feed_id}",
                "title": f"Cloud rss {feed_id}",
                "content": f"Cloud rss {feed_id}",
                "url": f"https://example.test/rss/{feed_id}",
                "published": bridge._now_iso(config),
                "source": f"trendradar_rss_{feed_id}",
                "type": "rss",
                "source_kind": "rss",
                "source_id": feed_id,
                "source_name": f"RSS {feed_id}",
                "rank": 1,
                "rank_highlight": bool(config.get("rank_threshold") and config.get("rank_threshold") >= 1),
                "score": 79,
                "first_seen": bridge._now_iso(config),
                "last_seen": bridge._now_iso(config),
                "matched_reason": f"RSS {feed_id}",
            })
        return items[: int(config.get("max_items_per_source", 30))], []

    bridge.fetch_trending = fake_fetch_trending  # type: ignore[assignment]
    bridge._fetch_rss_items = fake_fetch_rss_items  # type: ignore[assignment]

    temp_dir = tempfile.mkdtemp(prefix="auto-podcast-trendradar-settings-")
    try:
        base = make_base_config()
        result = bridge.run_once(base, temp_dir)
        verify_meta_config(result, base)

        assert_true(captured_fetches[-1]["platform_ids"] == ["source_a"], "enabled_platforms not applied")
        assert_true(captured_fetches[-1]["proxy_url"] == base["proxy_url"], "proxy_url not applied")
        assert_true(captured_fetches[-1]["api_url"] == base["api_url"], "api_url not applied")
        assert_true(captured_fetches[-1]["request_interval"] == 123, "crawler_request_interval not applied")
        assert_true(captured_rss[-1]["rss_timeout"] == 11, "rss_timeout not passed")
        assert_true(captured_rss[-1]["rss_request_interval"] == 77, "rss_request_interval not passed")
        assert_true(captured_rss[-1]["rss_proxy_enabled"] is True, "rss_proxy_enabled not passed")
        assert_true(captured_rss[-1]["rss_proxy_url"] == base["rss_proxy_url"], "rss_proxy_url not passed")
        assert_true(captured_rss[-1]["freshness_days"] == 9, "freshness_days not passed")
        assert_true(result["meta"]["rank_highlight_count"] >= 1, "rank_threshold not applied")
        assert_true(result["meta"]["generated_at"].endswith("+00:00"), "timezone not applied")
        assert_true({item.get("keyword_tag") for item in result["items"]} == {"AI", "Cloud"}, "keyword filter or max_news_per_keyword not applied")

        disabled = {**base, "platforms_enabled": False, "rss_enabled": False, "enabled_rss_feeds": []}
        before_fetch_count = len(captured_fetches)
        disabled_result = bridge.run_once(disabled, temp_dir)
        assert_true(len(captured_fetches) == before_fetch_count, "platforms_enabled false still fetched platforms")
        assert_true(disabled_result["items"] == [], "disabled sources should return no items")

        source_switch = {**base, "enabled_platforms": ["source_b"], "rss_enabled": False, "max_items_per_source": 1}
        switched_result = bridge.run_once(source_switch, temp_dir)
        assert_true(captured_fetches[-1]["platform_ids"] == ["source_b"], "source switch not applied")
        assert_true(all(item["source_id"] == "source_b" for item in switched_result["items"]), "wrong platform after source switch")

        standalone = {
            **base,
            "enabled_rss_feeds": [],
            "max_items_per_source": 3,
            "display_standalone_enabled": True,
            "standalone_platforms": ["source_a"],
            "standalone_max_items": 1,
        }
        standalone_result = bridge.run_once(standalone, temp_dir)
        assert_true(standalone_result["meta"]["standalone"]["added"] == 1, "standalone settings not applied")
        assert_true(any(item.get("standalone") for item in standalone_result["items"]), "standalone item not emitted")

        platform_topics = {**base, "report_display_mode": "platform"}
        platform_topics_result = bridge.run_once(platform_topics, temp_dir)
        assert_true(platform_topics_result["meta"]["topics"][0]["name"] in {"来源 A", "RSS feed_a"}, "report_display_mode platform not applied")

        bridge.run_once(base, temp_dir)
        incremental_result = bridge.run_once({**base, "report_mode": "incremental"}, temp_dir)
        assert_true(incremental_result["items"] == [], "report_mode incremental did not filter already seen items")

        captured_ai: Dict[str, Any] = {}

        def fake_ai_filter(items, config, user_data_dir=None):
            captured_ai.update(config)
            marked = []
            for item in items[:2]:
                next_item = dict(item)
                next_item["ai_filter_tag"] = "AI"
                next_item["ai_filter_score"] = 0.91
                marked.append(next_item)
            return marked, {
                "enabled": True,
                "total_processed": len(items),
                "total_matched": len(marked),
                "model": config.get("ai_model"),
                "tags": [{"tag": "AI", "count": len(marked)}],
            }

        bridge._apply_ai_filter = fake_ai_filter  # type: ignore[assignment]
        ai_config = {
            **base,
            "filter_method": "ai",
            "ai_available": True,
            "ai_api_key_set": True,
            "ai_provider_source": "app",
            "ai_model": "openai/gpt-4.1-mini",
            "ai_api_base": "https://api.example.test/v1",
            "ai_timeout": 33,
            "ai_temperature": 0.2,
            "ai_max_tokens": 1234,
            "ai_num_retries": 2,
            "ai_fallback_models": ["openai/gpt-4.1-nano"],
            "ai_filter_batch_size": 3,
            "ai_filter_batch_interval": 0,
            "ai_filter_min_score": 0.8,
            "ai_filter_reclassify_threshold": 0.4,
            "ai_filter_prompt_file": "custom_prompt.txt",
            "ai_filter_extract_prompt_file": "custom_extract.txt",
            "ai_filter_update_tags_prompt_file": "custom_update.txt",
        }
        ai_result = bridge.run_once(ai_config, temp_dir)
        verify_meta_config(ai_result, ai_config)
        for key in [
            "ai_model",
            "ai_api_base",
            "ai_timeout",
            "ai_temperature",
            "ai_max_tokens",
            "ai_num_retries",
            "ai_fallback_models",
            "ai_filter_batch_size",
            "ai_filter_batch_interval",
            "ai_filter_min_score",
            "ai_filter_reclassify_threshold",
            "ai_filter_prompt_file",
            "ai_filter_extract_prompt_file",
            "ai_filter_update_tags_prompt_file",
        ]:
            assert_true(captured_ai.get(key) == ai_config[key], f"{key} not passed to AI filter")

        print("TrendRadar discovery settings verified")
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
