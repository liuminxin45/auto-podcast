"""
Test module for stages node
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.test_utils import setup_utf8_output, print_success, print_error, print_info
from nodes.stages.node import run
from nodes.stages.config import StagesConfig
from tests.mock_data import create_state_for_node

setup_utf8_output()


def test_stages_node():
    """Test stages node with mock data"""
    print_info("Testing stages node...")
    
    state = create_state_for_node("stages")
    
    config = StagesConfig(words_per_minute=150, max_segment_duration=120)
    dialogue_count = len(state["script"]["dialogue"])
    result = run(state, config)
    
    assert "stages" in result, "Should have stages"
    assert isinstance(result["stages"], list), "stages should be a list"
    assert len(result["stages"]) == dialogue_count, "Should have one stage per dialogue line"
    
    for stage in result["stages"]:
        assert "order" in stage, "Each stage should have order"
        assert "speaker" in stage, "Each stage should have speaker"
        assert "text" in stage, "Each stage should have text"
        assert isinstance(stage["order"], int), "order should be an integer"
    
    state = result

    
    print_success("Stages node test passed: {len(state['stages'])} stages created")
    return True


if __name__ == "__main__":
    try:
        test_stages_node()
        sys.exit(0)
    except AssertionError as e:
        print_error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
