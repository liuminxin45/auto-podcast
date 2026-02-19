from typing import Dict, Any
from nodes.preprocess.config import PreprocessConfig


def run(state: Dict[str, Any], config: PreprocessConfig = None) -> Dict[str, Any]:
    config = config or PreprocessConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    # In auto_execute mode, skip min_content_length filter
    # Hotlist items only have titles (short content) and are still valid
    runtime_config = state.get("runtime_config", {})
    auto_execute = runtime_config.get("auto_execute", False)
    effective_min_length = 0 if auto_execute else config.min_content_length

    logs.append("[PreprocessNode] Starting preprocess")
    if auto_execute:
        logs.append(f"[PreprocessNode] Auto-execute mode: min_content_length set to 0 (hotlist items allowed)")
    raw = state.get("raw_contents", [])
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
    logs.append(f"[PreprocessNode] Kept {len(cleaned)} items")
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
