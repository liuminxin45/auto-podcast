from typing import Dict, Any
from nodes.manual.config import ManualConfig


def run(state: Dict[str, Any], config: ManualConfig = None) -> Dict[str, Any]:
    """Manual input node - 灵感收集箱：手动输入素材"""
    config = config or ManualConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    _start_ts = datetime.now().isoformat()
    logs.append(f"[ManualNode] ========== 节点启动 ==========")
    logs.append(f"[ManualNode] 启动时间: {_start_ts}")
    logs.append(f"[ManualNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[ManualNode] 配置: news_items={len(config.news_items)} items")
    _dbg = state.get("runtime_config", {}).get("debug_mode", {}).get("enabled", False)
    logs.append(f"[ManualNode] debug_mode={_dbg} (此节点不使用LLM, 不受debug_mode影响)")
    
    # 处理手动输入的新闻
    manual_contents = []
    
    if not config.news_items:
        logs.append("[ManualNode] No manual items provided (this is fine, merge will handle it)")
    else:
        logs.append(f"[ManualNode] Processing {len(config.news_items)} manual news items")
        
        for idx, item in enumerate(config.news_items):
            if not isinstance(item, dict):
                logs.append(f"[ManualNode] Skipping invalid item at index {idx}")
                continue
            
            # 构建标准化的新闻条目
            news_item = {
                "title": item.get("title", f"Manual News {idx + 1}"),
                "content": item.get("content", ""),
                "url": item.get("url", ""),
                "published": item.get("published", ""),
                "source": "manual_input",
                "type": "manual",
            }
            manual_contents.append(news_item)
        
        logs.append(f"[ManualNode] Added {len(manual_contents)} manual news items")
    
    state["manual_contents"] = manual_contents
    _elapsed = _time.time() - _t0
    logs.append(f"[ManualNode] ========== 节点完成 ==========")
    logs.append(f"[ManualNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    logs.append(f"[ManualNode] 输出: manual_contents={len(manual_contents)} items")
    if manual_contents:
        sample_titles = [item.get('title', 'Untitled')[:40] for item in manual_contents[:3]]
        logs.append(f"[ManualNode] 样本标题: {sample_titles}")
    logs.append(f"[ManualNode] 错误数: {len([e for e in errors if e.get('node') == 'manual'])}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state
