from typing import Dict, Any
from nodes.source_selector.config import SourceSelectorConfig


def run(state: Dict[str, Any], config: SourceSelectorConfig = None) -> Dict[str, Any]:
    """Source selector node - 选择使用fetch还是manual的内容"""
    config = config or SourceSelectorConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append(f"[SourceSelector] Selected source type: {config.source_type}")
    
    # 将选择的来源类型保存到state中，供后续节点使用
    state["selected_source_type"] = config.source_type
    state["logs"] = logs
    state["errors"] = errors
    
    return state
