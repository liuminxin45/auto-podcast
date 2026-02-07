from typing import Dict, Any
from nodes.research.config import ResearchConfig


def run(state: Dict[str, Any], config: ResearchConfig = None) -> Dict[str, Any]:
    config = config or ResearchConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[ResearchNode] Starting research")
    cleaned = state.get("cleaned_contents", [])
    researched = []

    try:
        for item in cleaned:
            researched_item = {
                **item,
                "research_notes": "",
                "key_points": [],
                "verified": False,
            }
            if config.enable_web_search:
                researched_item["research_notes"] = f"Research notes for: {item.get('title', '')}"
            researched.append(researched_item)
    except Exception as e:
        errors.append({"node": "research", "message": str(e), "detail": str(e)})

    state["researched_contents"] = researched
    logs.append(f"[ResearchNode] Researched {len(researched)} items")
    state["logs"] = logs
    state["errors"] = errors
    return state
