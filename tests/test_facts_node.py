from nodes.facts.config import FactsConfig
from nodes.facts.node import run as facts_run
from tests.mock_data import create_base_state, create_mock_cleaned_contents, create_mock_materials


def test_facts_node_uses_selected_materials_first():
    state = create_base_state()
    state["selected_materials"] = create_mock_materials()
    state["cleaned_contents"] = []
    result = facts_run(state, FactsConfig(max_facts=3, selected_topic_count=2))
    assert len(result["facts"]) == 2
    assert len(result["selected_topics"]) == 2
    assert result["run_report"]["facts"]["total"] == 2


def test_facts_node_falls_back_to_cleaned_contents():
    state = create_base_state()
    state["cleaned_contents"] = create_mock_cleaned_contents()
    result = facts_run(state, FactsConfig(max_facts=2, selected_topic_count=2))
    assert len(result["facts"]) == 2
    assert result["selected_materials"] == state["cleaned_contents"]
