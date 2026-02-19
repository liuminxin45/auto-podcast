from typing import Dict, Any
from nodes.research.config import ResearchConfig
from protocol.llm_client import LLMClient
import json


def run(state: Dict[str, Any], config: ResearchConfig = None) -> Dict[str, Any]:
    config = config or ResearchConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    _start_ts = datetime.now().isoformat()
    runtime_config = state.get("runtime_config", {})
    organize_config = runtime_config.get("organize", {})
    is_ai_mode = organize_config.get("mode") == "ai"
    auto_execute = runtime_config.get("auto_execute", False)
    cleaned = state.get("cleaned_contents", [])
    
    logs.append(f"[ResearchNode] ========== 节点启动 ==========")
    logs.append(f"[ResearchNode] 启动时间: {_start_ts}")
    logs.append(f"[ResearchNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[ResearchNode] 输入: cleaned_contents={len(cleaned)} items")
    logs.append(f"[ResearchNode] 配置: auto_execute={auto_execute}, is_ai_mode={is_ai_mode}")
    
    # Get LLM config from script node if research node config is not set
    if auto_execute and is_ai_mode:
        script_config = runtime_config.get("script", {})
        if not config.api_key and script_config.get("api_key"):
            config.api_key = script_config.get("api_key")
            config.api_base = script_config.get("api_base", "")
            config.llm_model = script_config.get("llm_model", "gpt-4o-mini")
            config.temperature = script_config.get("temperature", 0.5)
            logs.append(f"[ResearchNode] Using LLM config from script node: {config.api_base[:30]}... / {config.llm_model}")
    
    debug_mode = runtime_config.get("debug_mode", {}).get("enabled", False)
    if debug_mode:
        logs.append(f"[ResearchNode] ⚡ DEBUG MODE ACTIVE")
        logs.append(f"[ResearchNode]   效果说明: Prompt截断至150字, max_tokens=100, timeout=20s, 精简JSON输出")
    else:
        logs.append(f"[ResearchNode] 运行模式: 正常 (debug_mode=False)")
    logs.append(f"[ResearchNode] LLM config: api_key={'SET' if config.api_key else 'NOT SET'}, api_base={config.api_base}")
    researched = []

    try:
        if auto_execute:
            # In auto_execute mode, pass all items through without LLM calls.
            # topic_selection will do AI-powered filtering by topic on the full pool.
            logs.append("[ResearchNode] Auto-execute模式: 直传所有条目 (topic_selection将按主题过滤)")
            for item in cleaned:
                researched.append({
                    **item,
                    "research_notes": "",
                    "key_points": [],
                    "verified": False,
                })
            logs.append(f"[ResearchNode] 直传完成: {len(researched)} items")
        elif is_ai_mode and config.api_key and config.api_base:
            logs.append(f"[ResearchNode] 启动LLM深度分析, 共 {len(cleaned)} 条内容...")
            if debug_mode:
                logs.append(f"[ResearchNode] ⚡ DEBUG: 每条内容使用精简Prompt (单个关键点), 超时=20s, max_tokens=100")
            researched = _ai_research_with_llm(cleaned, config, logs, debug_mode=debug_mode)
            logs.append(f"[ResearchNode] LLM分析完成")
        else:
            logs.append(f"[ResearchNode] 基础模式 (无LLM, api_key={bool(config.api_key)}, api_base={bool(config.api_base)})")
            for item in cleaned:
                researched.append({
                    **item,
                    "research_notes": "",
                    "key_points": [],
                    "verified": False,
                })
            logs.append(f"[ResearchNode] 处理完成: {len(researched)} items")
    except Exception as e:
        logs.append(f"[ResearchNode] ✗ 执行异常: {type(e).__name__}: {str(e)}")
        import traceback
        logs.append(f"[ResearchNode] Traceback: {traceback.format_exc()}")
        errors.append({"node": "research", "message": str(e), "detail": str(e)})

    state["researched_contents"] = researched
    _elapsed = _time.time() - _t0
    _end_ts = datetime.now().isoformat()
    verified_count = sum(1 for item in researched if item.get('verified'))
    logs.append(f"[ResearchNode] ========== 节点完成 ==========")
    logs.append(f"[ResearchNode] 完成时间: {_end_ts} | 耗时: {_elapsed:.2f}s")
    logs.append(f"[ResearchNode] 输出: researched_contents={len(researched)} items")
    logs.append(f"[ResearchNode] 分析统计: AI验证={verified_count}, 未验证={len(researched)-verified_count}")
    logs.append(f"[ResearchNode] 错误数: {len([e for e in errors if e.get('node') == 'research'])}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state


def _ai_research_with_llm(items: list, config: ResearchConfig, logs: list, debug_mode: bool = False) -> list:
    """Use LLM to extract key points and research notes from content."""
    researched = []
    
    try:
        with LLMClient(config.api_base, config.api_key, config.llm_model, config.temperature, debug_mode=debug_mode) as client:
            for idx, item in enumerate(items):
                logs.append(f"[ResearchNode] AI analyzing item {idx+1}/{len(items)}: {item.get('title', 'Untitled')[:50]}...")
                
                if debug_mode:
                    prompt = f"""标题：{item.get('title', '')[:50]}

提取1个关键点，输出JSON: {{"key_point":"一句话"}}"""
                else:
                    prompt = f"""Analyze the following content and extract:
1. 3-5 key points (important facts, insights, or findings)
2. A brief research note (2-3 sentences summary)

Content Title: {item.get('title', '')}
Content: {item.get('content', '')[:1000]}

Respond in JSON format:
{{
  "key_points": ["point1", "point2", "point3"],
  "research_notes": "summary text"
}}"""
                
                try:
                    response = client.call(
                        [{"role": "user", "content": prompt}],
                        timeout=20 if debug_mode else 30,
                        max_tokens=100 if debug_mode else None,
                        logs=logs
                    )
                    
                    content = client.extract_content(response)
                    result = json.loads(content)
                    
                    if debug_mode:
                        researched_item = {
                            **item,
                            "research_notes": "",
                            "key_points": [result.get("key_point", "")],
                            "verified": True,
                        }
                    else:
                        researched_item = {
                            **item,
                            "research_notes": result.get("research_notes", ""),
                            "key_points": result.get("key_points", []),
                            "verified": True,
                        }
                    logs.append(f"[ResearchNode] ✓ Extracted {len(researched_item['key_points'])} key points")
                except json.JSONDecodeError:
                    logs.append(f"[ResearchNode] ⚠ JSON parse failed, using raw response")
                    researched_item = {
                        **item,
                        "research_notes": content[:200] if content else "",
                        "key_points": [],
                        "verified": False,
                    }
                except Exception as e:
                    logs.append(f"[ResearchNode] ✗ LLM call failed for item {idx+1}: {str(e)}")
                    researched_item = {
                        **item,
                        "research_notes": "",
                        "key_points": [],
                        "verified": False,
                    }
                
                researched.append(researched_item)
    except Exception as e:
        logs.append(f"[ResearchNode] LLM client error: {str(e)}")
        raise
    
    return researched
