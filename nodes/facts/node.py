from typing import Any

from nodes.facts.config import FactsConfig
from protocol.morning_news import build_fact_cards, build_run_report, select_news_topics
from protocol.node_runner import NodeContext


def run(state: dict[str, Any], config: FactsConfig = None) -> dict[str, Any]:
    config = config or FactsConfig()
    ctx = NodeContext("FactsNode", state)
    materials = state.get("selected_materials", [])
    if not materials and config.allow_cleaned_fallback:
        materials = state.get("cleaned_contents", [])
    if not materials:
        materials = state.get("source_inputs", [])

    ctx.log_start(
        f"输入: materials={len(materials)}, max_facts={config.max_facts}, selected_topic_count={config.selected_topic_count}"
    )

    try:
        if not materials:
            ctx.add_error("facts", "No selected materials or cleaned contents available for fact cards")
            ctx.log_end("输出: facts=0")
            return ctx.finalize(state)

        facts = build_fact_cards(materials, limit=config.max_facts)
        state["facts"] = facts
        state["selected_topics"] = select_news_topics(facts, config.selected_topic_count)
        if not state.get("selected_materials"):
            state["selected_materials"] = materials
        if not state.get("source_inputs"):
            state["source_inputs"] = materials
        build_run_report(state)
        ctx.log(f"事实卡片生成完成: facts={len(facts)}, selected_topics={len(state['selected_topics'])}")
    except Exception as exc:
        ctx.add_error("facts", str(exc), detail=str(exc))

    ctx.log_end(
        f"输出: facts={len(state.get('facts', []))}, selected_topics={len(state.get('selected_topics', []))}"
    )
    return ctx.finalize(state)
