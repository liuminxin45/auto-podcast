from typing import Dict, Any
from nodes.preprocess.config import PreprocessConfig


def run(state: Dict[str, Any], config: PreprocessConfig = None) -> Dict[str, Any]:
    config = config or PreprocessConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    runtime_config = state.get("runtime_config", {})
    auto_execute = runtime_config.get("auto_execute", False)
    effective_min_length = 0 if auto_execute else config.min_content_length
    raw = state.get("raw_contents", [])
    
    logs.append(f"[PreprocessNode] ========== 节点启动 ==========")
    logs.append(f"[PreprocessNode] 启动时间: {datetime.now().isoformat()}")
    logs.append(f"[PreprocessNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[PreprocessNode] 输入: raw_contents={len(raw)} items")
    logs.append(f"[PreprocessNode] 配置: min_length={effective_min_length}, max_length={config.max_content_length}, remove_duplicates={config.remove_duplicates}")
    _dbg = runtime_config.get("debug_mode", {}).get("enabled", False)
    logs.append(f"[PreprocessNode] debug_mode={_dbg} (此节点不使用LLM, 不受debug_mode影响)")
    if auto_execute:
        logs.append(f"[PreprocessNode] Auto-execute mode: min_content_length set to 0 (hotlist items allowed)")
    cleaned = []

    try:
        for item in raw:
            content = item.get("content", "")
            if len(content) < effective_min_length:
                continue
            if len(content) > config.max_content_length:
                content = content[:config.max_content_length]
                item = {**item, "content": content}
            cleaned.append(item)

        if config.remove_duplicates and len(cleaned) > 1:
            cleaned = _dedup(cleaned, config.similarity_threshold)
    except Exception as e:
        errors.append({"node": "preprocess", "message": str(e), "detail": str(e)})

    state["cleaned_contents"] = cleaned
    _elapsed = _time.time() - _t0
    filtered_count = len(raw) - len(cleaned)
    logs.append(f"[PreprocessNode] ========== 节点完成 ==========")
    logs.append(f"[PreprocessNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    logs.append(f"[PreprocessNode] 输出: cleaned_contents={len(cleaned)} items")
    logs.append(f"[PreprocessNode] 过滤统计: 输入{len(raw)}, 保留{len(cleaned)}, 过滤{filtered_count}")
    logs.append(f"[PreprocessNode] 错误数: {len([e for e in errors if e.get('node') == 'preprocess'])}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state


def _dedup(items, threshold):
    seen_titles = set()
    unique = []
    for item in items:
        title = item.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            unique.append(item)
    return unique
