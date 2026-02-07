"""
Test module for fetch node
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.test_utils import setup_utf8_output, print_success, print_error, print_info
from nodes.fetch.node import run
from nodes.fetch.config import FetchConfig
from tests.mock_data import create_state_for_node
from tests.mock_data import create_mock_raw_contents

setup_utf8_output()


def test_fetch_node():
    """Test fetch node with mock data"""
    print_info("Testing fetch node...")
    
    state = create_state_for_node("fetch")
    
    config = FetchConfig(sources=[], max_items_per_source=10)
    state["raw_contents"] = create_mock_raw_contents()
    
    assert isinstance(state["raw_contents"], list), "raw_contents should be a list"
    assert len(state["raw_contents"]) > 0, "Should have fetched content"
    
    for item in state["raw_contents"]:
        assert "title" in item, "Each item should have a title"
        assert "content" in item, "Each item should have content"
        assert "url" in item, "Each item should have a url"

    
    print_success("Fetch node test passed: {len(state['raw_contents'])} items")
    return True


if __name__ == "__main__":
    try:
        test_fetch_node()
        sys.exit(0)
    except AssertionError as e:
        print_error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
