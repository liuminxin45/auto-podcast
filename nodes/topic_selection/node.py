from typing import Dict, Any, List
from nodes.topic_selection.config import TopicSelectionConfig


def run(state: Dict[str, Any], config: TopicSelectionConfig = None) -> Dict[str, Any]:
    config = config or TopicSelectionConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[TopicSelectionNode] Starting topic selection")
    contents = state.get("researched_contents", [])

    try:
        if not contents:
            errors.append({"node": "topic_selection", "message": "No content for topic selection"})
            state["logs"] = logs
            state["errors"] = errors
            return state

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
