from typing import Dict, Any, List
from nodes.merge.config import MergeConfig


def run(state: Dict[str, Any], config: MergeConfig = None) -> Dict[str, Any]:
    """Merge node - 创作素材池：整合 Fetch 与 Manual 两侧的内容"""
    config = config or MergeConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    fetch_contents = state.get("fetch_contents", [])
    manual_contents = state.get("manual_contents", [])
    
    logs.append(f"[MergeNode] ========== 节点启动 ==========")
    logs.append(f"[MergeNode] 启动时间: {datetime.now().isoformat()}")
    logs.append(f"[MergeNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[MergeNode] 输入: fetch_contents={len(fetch_contents)}, manual_contents={len(manual_contents)}")
    logs.append(f"[MergeNode] 配置: deduplicate={config.deduplicate}, similarity_threshold={config.similarity_threshold}")
    _dbg = state.get("runtime_config", {}).get("debug_mode", {}).get("enabled", False)
    logs.append(f"[MergeNode] debug_mode={_dbg} (此节点不使用LLM, 不受debug_mode影响)")

    # Tag sources for traceability
    for item in fetch_contents:
        item["_source_channel"] = "auto"
    for item in manual_contents:
        item["_source_channel"] = "manual"

    # Combine both channels
    merged = list(fetch_contents) + list(manual_contents)

    # Deduplicate by title similarity
    if config.deduplicate and len(merged) > 1:
        before = len(merged)
        merged = _deduplicate(merged, config.similarity_threshold)
        removed = before - len(merged)
        if removed > 0:
            logs.append(f"[MergeNode] Removed {removed} duplicate(s)")

    if len(merged) == 0:
        logs.append("[MergeNode] Warning: No content from either source. Pipeline may produce empty results.")
    else:
        logs.append(f"[MergeNode] Final merged pool: {len(merged)} items")

    state["raw_contents"] = merged
    _elapsed = _time.time() - _t0
    auto_count = sum(1 for item in merged if item.get('_source_channel') == 'auto')
    manual_count = sum(1 for item in merged if item.get('_source_channel') == 'manual')
    logs.append(f"[MergeNode] ========== 节点完成 ==========")
    logs.append(f"[MergeNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    logs.append(f"[MergeNode] 输出: raw_contents={len(merged)} items")
    logs.append(f"[MergeNode] 来源分布: auto={auto_count}, manual={manual_count}")
    logs.append(f"[MergeNode] 错误数: {len([e for e in errors if e.get('node') == 'merge'])}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state


def _deduplicate(items: List[Dict[str, Any]], threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Title-based deduplication. Uses exact match when threshold >= 1.0,
    otherwise falls back to SequenceMatcher ratio."""
    from difflib import SequenceMatcher

    unique: List[Dict[str, Any]] = []
    seen_titles: List[str] = []
    for item in items:
        title = item.get("title", "").strip().lower()
        if not title:
            unique.append(item)
            continue
        if threshold >= 1.0:
            if title not in seen_titles:
                seen_titles.append(title)
                unique.append(item)
        else:
            is_dup = any(
                SequenceMatcher(None, title, s).ratio() >= threshold
                for s in seen_titles
            )
            if not is_dup:
                seen_titles.append(title)
                unique.append(item)
    return unique
