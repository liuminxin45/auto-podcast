from typing import Dict, Any, List
from datetime import datetime, timedelta
from nodes.topic_selection.config import TopicSelectionConfig
from protocol.llm_client import LLMClient, LLMError


def run(state: Dict[str, Any], config: TopicSelectionConfig = None) -> Dict[str, Any]:
    config = config or TopicSelectionConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    _t0 = _time.time()
    runtime_config = state.get("runtime_config", {})
    organize_config = runtime_config.get("organize", {})
    is_ai_mode = organize_config.get("mode") == "ai"
    auto_execute = runtime_config.get("auto_execute", False)
    contents = state.get("researched_contents", [])
    
    logs.append(f"[TopicSelectionNode] ========== 节点启动 ==========")
    logs.append(f"[TopicSelectionNode] 启动时间: {datetime.now().isoformat()}")
    logs.append(f"[TopicSelectionNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[TopicSelectionNode] 输入: researched_contents={len(contents)} items")
    
    # Get LLM config from script node if not set
    if auto_execute and is_ai_mode:
        script_config = runtime_config.get("script", {})
        if not config.api_key and script_config.get("api_key"):
            config.api_key = script_config.get("api_key")
            config.api_base = script_config.get("api_base", "")
            config.llm_model = script_config.get("llm_model", "gpt-4o-mini")
            config.temperature = script_config.get("temperature", 0.3)
            logs.append(f"[TopicSelectionNode] Using LLM config from script node: {config.api_base[:30]}... / {config.llm_model}")

    # In auto_execute mode, always use analyze_relevance with target_topic from runtime_config
    discover_config = runtime_config.get("discover", {})
    target_topic_from_runtime = discover_config.get("target_topic", "")
    time_range_from_runtime = discover_config.get("time_range_hours", 72)

    if auto_execute and target_topic_from_runtime:
        mode = "analyze_relevance"
        config.target_topic = target_topic_from_runtime
        config.time_range_hours = time_range_from_runtime
        config.max_items = discover_config.get("max_items", 10)
    else:
        mode = config.mode

    debug_mode = runtime_config.get("debug_mode", {}).get("enabled", False)
    if debug_mode:
        logs.append(f"[TopicSelectionNode] ⚡ DEBUG MODE ACTIVE")
        logs.append(f"[TopicSelectionNode]   效果说明: batch_size=1 (逐条分析), Prompt截断至150字, max_tokens=200")
    else:
        logs.append(f"[TopicSelectionNode] 运行模式: 正常 (debug_mode=False)")
    logs.append(f"[TopicSelectionNode] 配置: mode={mode}, AI={is_ai_mode}, auto={auto_execute}")
    if auto_execute and target_topic_from_runtime:
        logs.append(f"[TopicSelectionNode] Target topic: '{target_topic_from_runtime}', time_range={time_range_from_runtime}h, max_items={config.max_items}")

    try:
        if not contents:
            errors.append({"node": "topic_selection", "message": "No content for topic selection"})
            state["logs"] = logs
            state["errors"] = errors
            return state

        if mode == "analyze_relevance":
            # Auto selection mode: select multiple relevant materials by topic
            logs.append(f"[TopicSelectionNode] Auto-selection for topic: {config.target_topic}")
            if debug_mode:
                logs.append(f"[TopicSelectionNode] ⚡ DEBUG: 将对 {len(contents)} 条内容逐一调用LLM评分")
            selected, rejected = _analyze_relevance(contents, config, logs, debug_mode=debug_mode)

            if auto_execute:
                # In auto_execute, selected materials go to organized layer as inputs
                state["selected_materials"] = selected
                state["selected_topic"] = {
                    "title": config.target_topic,
                    "description": f"围绕\"{config.target_topic}\"筛选的 {len(selected)} 条相关素材",
                    "keywords": [],
                }
                logs.append(f"[TopicSelectionNode] ✓ Selected {len(selected)} materials for topic '{config.target_topic}'")
            else:
                state["auto_selected_items"] = selected
                state["auto_rejected_items"] = rejected
                logs.append(f"[TopicSelectionNode] Selected {len(selected)}, Rejected {len(rejected)}")
        else:
            # Traditional cluster mode with LLM scoring if AI mode
            if auto_execute and is_ai_mode:
                logs.append("[TopicSelectionNode] Using AI-powered clustering")
                config.use_llm_scoring = True
            
            logs.append(f"[TopicSelectionNode] Clustering {len(contents)} items (min_cluster_size={config.min_cluster_size})")
            clusters = _cluster_contents(contents, config, logs)
            
            if clusters:
                logs.append(f"[TopicSelectionNode] Found {len(clusters)} clusters")
                for i, cluster in enumerate(clusters):
                    logs.append(f"[TopicSelectionNode]   Cluster {i+1}: {len(cluster.get('items', []))} items - {cluster.get('title', 'Unknown')}")
                
                best = max(clusters, key=lambda c: len(c["items"]))
                state["selected_topic"] = {
                    "title": best.get("title", ""),
                    "description": best.get("description", ""),
                    "keywords": best.get("keywords", []),
                }
                state["selected_materials"] = best.get("items", [])
                logs.append(f"[TopicSelectionNode] ✓ Selected cluster: '{state['selected_topic']['title']}' with {len(state['selected_materials'])} materials")
            else:
                logs.append("[TopicSelectionNode] No clusters formed, using all contents")
                state["selected_topic"] = {"title": "General Topic", "description": "", "keywords": []}
                state["selected_materials"] = contents
                logs.append(f"[TopicSelectionNode] Using all {len(contents)} items as materials")
    except Exception as e:
        errors.append({"node": "topic_selection", "message": str(e), "detail": str(e)})
        logs.append(f"[TopicSelectionNode] Error: {str(e)}")

    selected_topic = state.get("selected_topic", {})
    selected_materials = state.get("selected_materials", [])
    _elapsed = _time.time() - _t0
    logs.append(f"[TopicSelectionNode] ========== 节点完成 ==========")
    logs.append(f"[TopicSelectionNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    logs.append(f"[TopicSelectionNode] 输出: selected_topic='{selected_topic.get('title', 'N/A')[:50]}', selected_materials={len(selected_materials)} items")
    if selected_materials:
        sample_titles = [m.get('title', 'Untitled')[:40] for m in selected_materials[:3]]
        logs.append(f"[TopicSelectionNode] 样本素材: {sample_titles}")
    logs.append(f"[TopicSelectionNode] 错误数: {len([e for e in errors if e.get('node') == 'topic_selection'])}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state


def _cluster_contents(contents: List[Dict], config: TopicSelectionConfig, logs: List[str]) -> List[Dict]:
    if len(contents) < config.min_cluster_size:
        logs.append(f"[TopicSelection] Content count ({len(contents)}) < min_cluster_size ({config.min_cluster_size}), creating single cluster")
        return [{"title": "General Topic", "description": "", "keywords": [], "items": contents}]

    logs.append("[TopicSelection] Starting TF-IDF vectorization...")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans

    texts = [item.get("content", "") for item in contents]
    vectorizer = TfidfVectorizer(max_features=100)
    X = vectorizer.fit_transform(texts)
    logs.append(f"[TopicSelection] Vectorized {len(texts)} documents into {X.shape[1]} features")

    n_clusters = max(1, min(3, len(contents) // config.min_cluster_size))
    logs.append(f"[TopicSelection] Running K-Means with {n_clusters} clusters...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)
    logs.append(f"[TopicSelection] K-Means clustering completed")

    clusters = []
    for i in range(n_clusters):
        cluster_items = [contents[j] for j in range(len(contents)) if labels[j] == i]
        if cluster_items:
            # Get top keywords from cluster
            cluster_title = f"Topic Cluster {i+1}"
            if cluster_items:
                sample_titles = [item.get('title', '')[:30] for item in cluster_items[:3]]
                logs.append(f"[TopicSelection] Cluster {i+1}: {len(cluster_items)} items, samples: {sample_titles}")
            
            clusters.append({
                "title": cluster_title,
                "description": "",
                "keywords": [],
                "items": cluster_items,
            })
    return clusters


def _analyze_relevance(contents: List[Dict], config: TopicSelectionConfig, logs: List[str], debug_mode: bool = False) -> tuple:
    """Analyze content relevance using LLM. Returns (selected, rejected)."""
    logs.append(f"[TopicSelection] _analyze_relevance called with {len(contents)} items (debug_mode={debug_mode})")
    logs.append(f"[TopicSelection] Config: api_key={'SET' if config.api_key else 'NOT SET'}, api_base={config.api_base}, model={config.llm_model}")
    
    time_filtered = _filter_by_time(contents, config.time_range_hours)
    logs.append(f"[TopicSelection] Time filter: {len(time_filtered)}/{len(contents)} items within {config.time_range_hours}h")
    
    if not time_filtered:
        logs.append("[TopicSelection] No items after time filter, returning empty")
        return [], contents
    
    if not config.api_key or not config.api_base:
        logs.append(f"[TopicSelection] ⚠ No LLM config (api_key={bool(config.api_key)}, api_base={bool(config.api_base)}), skipping AI analysis")
        logs.append(f"[TopicSelection] Fallback: returning first {config.max_items} items without AI scoring")
        return time_filtered[:config.max_items], time_filtered[config.max_items:] + [c for c in contents if c not in time_filtered]
    
    try:
        llm_input_cap = max(config.max_items * 3, 20)
        llm_candidates = time_filtered[:llm_input_cap]
        skipped_candidates = time_filtered[llm_input_cap:]
        logs.append(f"[TopicSelection] LLM候选池: max_items={config.max_items} → 候选上限={llm_input_cap} (max_items*3)")
        if skipped_candidates:
            logs.append(
                f"[TopicSelection] LLM input capped: {len(llm_candidates)}/{len(time_filtered)} items (skipped={len(skipped_candidates)})"
            )

        logs.append(f"[TopicSelection] Starting LLM analysis with {len(llm_candidates)} items...")
        import time
        start_time = time.time()
        
        with LLMClient(config.api_base, config.api_key, config.llm_model, config.temperature, debug_mode=debug_mode) as client:
            logs.append("[TopicSelection] LLMClient initialized, calling _llm_batch_analyze...")
            analyzed = _llm_batch_analyze(llm_candidates, config, client, logs)
        
        elapsed = time.time() - start_time
        logs.append(f"[TopicSelection] LLM analysis completed in {elapsed:.2f}s")
        
        analyzed.sort(key=lambda x: x.get("_topic_score", 0), reverse=True)
        selected = [item for item in analyzed if item.get("_topic_decision") == "keep"][:config.max_items]
        rejected = [item for item in analyzed if item.get("_topic_decision") != "keep"]
        rejected += skipped_candidates
        rejected += [c for c in contents if c not in time_filtered]
        
        logs.append(f"[TopicSelection] ✓ LLM analysis result: {len(selected)} selected, {len(rejected)} rejected")
        return selected, rejected
    except Exception as e:
        logs.append(f"[TopicSelection] ✗ LLM analysis failed: {type(e).__name__}: {str(e)}")
        import traceback
        logs.append(f"[TopicSelection] Traceback: {traceback.format_exc()}")
        logs.append(f"[TopicSelection] Fallback: returning first {config.max_items} items without AI scoring")
        return time_filtered[:config.max_items], time_filtered[config.max_items:] + [c for c in contents if c not in time_filtered]


def _filter_by_time(contents: List[Dict], hours: int) -> List[Dict]:
    """Filter contents by publish time within specified hours.
    Items without a parseable publish time are included (benefit of the doubt)."""
    if hours <= 0:
        return contents
    
    cutoff = datetime.now() - timedelta(hours=hours)
    filtered = []
    
    for item in contents:
        pub_time = (item.get("published_at") or item.get("pubDate") or
                    item.get("pub_time") or item.get("published"))
        if not pub_time:
            # No publish time — include the item (hotlist items are always fresh)
            filtered.append(item)
            continue
        
        try:
            if isinstance(pub_time, str):
                pub_dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
            else:
                pub_dt = pub_time
            # Strip timezone for comparison if needed
            if pub_dt.tzinfo is not None:
                from datetime import timezone
                cutoff_aware = cutoff.replace(tzinfo=timezone.utc)
                if pub_dt >= cutoff_aware:
                    filtered.append(item)
            else:
                if pub_dt >= cutoff:
                    filtered.append(item)
        except Exception:
            # Unparseable time — include the item
            filtered.append(item)
    
    return filtered


def _llm_batch_analyze(contents: List[Dict], config: TopicSelectionConfig, client: LLMClient, logs: List[str]) -> List[Dict]:
    """Use LLM to analyze relevance in batches."""
    def create_prompt(batch: List[Dict]) -> str:
        if client.debug_mode:
            item = batch[0]
            title = item.get("title", "")[:50]
            content = item.get("content", "")[:50]
            
            prompt = f"""选题：{config.target_topic}

文章：{title}
摘要：{content}

输出JSON: {{"decision":"keep"或"drop","score":0-100}}"""
            return prompt
        
        prompt = f"""你是专业的内容主编。当前选题任务：{config.target_topic}
{'额外要求：' + config.focus_instruction if config.focus_instruction else ''}

请分析以下文章是否适合作为选题素材。

文章列表：
"""
        for idx, item in enumerate(batch):
            title = item.get("title", "")
            summary = item.get("summary", item.get("content", ""))[:120]
            prompt += f"{idx+1}. 标题：{title}\n   摘要：{summary}\n\n"
        
        prompt += """请对每篇文章输出JSON数组，格式：
[{"index": 1, "score": 0-100, "decision": "keep"或"drop", "reason": "一句话理由", "angle": "建议切入角度"}]

只输出JSON数组，不要其他内容。"""
        return prompt
    
    def parse_results(batch: List[Dict], parsed: List[Dict]) -> List[Dict]:
        if client.debug_mode:
            item = batch[0]
            if isinstance(parsed, dict):
                item["_topic_score"] = parsed.get("score", 0)
                item["_topic_decision"] = parsed.get("decision", "drop")
                item["_topic_reason"] = ""
                item["_topic_angle"] = ""
            else:
                item["_topic_score"] = 0
                item["_topic_decision"] = "drop"
                item["_topic_reason"] = ""
                item["_topic_angle"] = ""
            return [item]
        
        result_dict = {r.get("index", i+1): r for i, r in enumerate(parsed)}
        for idx, item in enumerate(batch):
            result = result_dict.get(idx+1, {"score": 0, "decision": "drop", "reason": "解析失败", "angle": ""})
            item["_topic_score"] = result.get("score", 0)
            item["_topic_decision"] = result.get("decision", "drop")
            item["_topic_reason"] = result.get("reason", "")
            item["_topic_angle"] = result.get("angle", "")
        return batch
    
    return client.batch_analyze(contents, create_prompt, parse_results, logs)


