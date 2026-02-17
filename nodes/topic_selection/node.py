from typing import Dict, Any, List
from datetime import datetime, timedelta
from nodes.topic_selection.config import TopicSelectionConfig
from protocol.llm_client import LLMClient, LLMError


def run(state: Dict[str, Any], config: TopicSelectionConfig = None) -> Dict[str, Any]:
    config = config or TopicSelectionConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    mode = config.mode
    logs.append(f"[TopicSelectionNode] Starting topic selection (mode={mode})")
    contents = state.get("researched_contents", [])

    try:
        if not contents:
            errors.append({"node": "topic_selection", "message": "No content for topic selection"})
            state["logs"] = logs
            state["errors"] = errors
            return state

        if mode == "analyze_relevance":
            # Auto selection mode for Discover layer
            logs.append(f"[TopicSelectionNode] Auto-selection for topic: {config.target_topic}")
            selected, rejected = _analyze_relevance(contents, config, logs)
            state["auto_selected_items"] = selected
            state["auto_rejected_items"] = rejected
            logs.append(f"[TopicSelectionNode] Selected {len(selected)}, Rejected {len(rejected)}")
        else:
            # Traditional cluster mode
            clusters = _cluster_contents(contents, config)
            best = max(clusters, key=lambda c: len(c["items"]))
            state["selected_topic"] = {
                "title": best.get("title", ""),
                "description": best.get("description", ""),
                "keywords": best.get("keywords", []),
            }
            state["selected_materials"] = best.get("items", [])
            logs.append(f"[TopicSelectionNode] Selected: {state['selected_topic']['title']}")
    except Exception as e:
        errors.append({"node": "topic_selection", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state


def _cluster_contents(contents: List[Dict], config: TopicSelectionConfig) -> List[Dict]:
    if len(contents) < config.min_cluster_size:
        return [{"title": "General Topic", "description": "", "keywords": [], "items": contents}]

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans

    texts = [item.get("content", "") for item in contents]
    vectorizer = TfidfVectorizer(max_features=100)
    X = vectorizer.fit_transform(texts)

    n_clusters = max(1, min(3, len(contents) // config.min_cluster_size))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)

    clusters = []
    for i in range(n_clusters):
        cluster_items = [contents[j] for j in range(len(contents)) if labels[j] == i]
        if cluster_items:
            clusters.append({
                "title": f"Topic {i+1}",
                "description": "",
                "keywords": [],
                "items": cluster_items,
            })
    return clusters


def _analyze_relevance(contents: List[Dict], config: TopicSelectionConfig, logs: List[str]) -> tuple:
    """Analyze content relevance using LLM. Returns (selected, rejected)."""
    time_filtered = _filter_by_time(contents, config.time_range_hours)
    logs.append(f"[TopicSelection] Time filter: {len(time_filtered)}/{len(contents)} items within {config.time_range_hours}h")
    
    if not time_filtered:
        return [], contents
    
    if not config.api_key or not config.api_base:
        logs.append("[TopicSelection] No LLM config, skipping AI analysis")
        return time_filtered[:config.max_items], time_filtered[config.max_items:] + [c for c in contents if c not in time_filtered]
    
    try:
        with LLMClient(config.api_base, config.api_key, config.llm_model, config.temperature) as client:
            analyzed = _llm_batch_analyze(time_filtered, config, client, logs)
        
        analyzed.sort(key=lambda x: x.get("_topic_score", 0), reverse=True)
        selected = [item for item in analyzed if item.get("_topic_decision") == "keep"][:config.max_items]
        rejected = [item for item in analyzed if item.get("_topic_decision") != "keep"]
        rejected += [c for c in contents if c not in time_filtered]
        
        logs.append(f"[TopicSelection] LLM analysis: {len(selected)} selected, {len(rejected)} rejected")
        return selected, rejected
    except Exception as e:
        logs.append(f"[TopicSelection] LLM analysis failed: {str(e)}")
        return time_filtered[:config.max_items], time_filtered[config.max_items:] + [c for c in contents if c not in time_filtered]


def _filter_by_time(contents: List[Dict], hours: int) -> List[Dict]:
    """Filter contents by publish time within specified hours."""
    if hours <= 0:
        return contents
    
    cutoff = datetime.now() - timedelta(hours=hours)
    filtered = []
    
    for item in contents:
        pub_time = item.get("published_at") or item.get("pubDate") or item.get("pub_time")
        if not pub_time:
            continue
        
        try:
            pub_dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00')) if isinstance(pub_time, str) else pub_time
            if pub_dt >= cutoff:
                filtered.append(item)
        except:
            continue
    
    return filtered


def _llm_batch_analyze(contents: List[Dict], config: TopicSelectionConfig, client: LLMClient, logs: List[str]) -> List[Dict]:
    """Use LLM to analyze relevance in batches."""
    def create_prompt(batch: List[Dict]) -> str:
        prompt = f"""你是专业的内容主编。当前选题任务：{config.target_topic}
{'额外要求：' + config.focus_instruction if config.focus_instruction else ''}

请分析以下文章是否适合作为选题素材。

文章列表：
"""
        for idx, item in enumerate(batch):
            title = item.get("title", "")
            summary = item.get("summary", item.get("content", ""))[:200]
            prompt += f"{idx+1}. 标题：{title}\n   摘要：{summary}\n\n"
        
        prompt += """请对每篇文章输出JSON数组，格式：
[{"index": 1, "score": 0-100, "decision": "keep"或"drop", "reason": "一句话理由", "angle": "建议切入角度"}]

只输出JSON数组，不要其他内容。"""
        return prompt
    
    def parse_results(batch: List[Dict], parsed: List[Dict]) -> List[Dict]:
        result_dict = {r.get("index", i+1): r for i, r in enumerate(parsed)}
        for idx, item in enumerate(batch):
            result = result_dict.get(idx+1, {"score": 0, "decision": "drop", "reason": "解析失败", "angle": ""})
            item["_topic_score"] = result.get("score", 0)
            item["_topic_decision"] = result.get("decision", "drop")
            item["_topic_reason"] = result.get("reason", "")
            item["_topic_angle"] = result.get("angle", "")
        return batch
    
    return client.batch_analyze(contents, create_prompt, parse_results, logs)


