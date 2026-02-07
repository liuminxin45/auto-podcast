from typing import Dict, Any, List
from nodes.stages.config import StagesConfig


def run(state: Dict[str, Any], config: StagesConfig = None) -> Dict[str, Any]:
    config = config or StagesConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])

    logs.append("[StagesNode] Starting segmentation")
    script = state.get("script", {})
    dialogue = script.get("dialogue", [])

    try:
        stages = []
        for i, line in enumerate(dialogue):
            text = line.get("text", "")
            word_count = len(text)
            duration = word_count / config.words_per_minute * 60
            stages.append({
                "order": i,
                "speaker": line.get("speaker", ""),
                "text": text,
                "estimated_duration": round(duration, 1),
            })
        state["stages"] = stages
        total = sum(s["estimated_duration"] for s in stages)
        logs.append(f"[StagesNode] {len(stages)} segments, ~{total:.0f}s total")
    except Exception as e:
        errors.append({"node": "stages", "message": str(e), "detail": str(e)})

    state["logs"] = logs
    state["errors"] = errors
    return state
