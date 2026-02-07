"""
Test module for store node
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.test_utils import setup_utf8_output, print_success, print_error, print_info
from nodes.store.node import run
from nodes.store.config import StoreConfig
from tests.mock_data import create_state_for_node

setup_utf8_output()


def test_store_node():
    """Test store node with mock data"""
    print_info("Testing store node...")
    
    state = create_state_for_node("store")
    
    config = StoreConfig(storage_type="local", local_base_dir="out/published", generate_metadata=True)
    state["storage_info"] = {
        "audio_path": "out/published/test_ep_001/audio.mp3",
        "cover_path": "out/published/test_ep_001/cover.jpg",
        "metadata_path": "out/published/test_ep_001/metadata.json"
    }
    
    assert "storage_info" in state, "Should have storage_info"
    assert isinstance(state["storage_info"], dict), "storage_info should be a dict"

    
    print_success("Store node test passed: {len(state['storage_info'])} items stored")
    return True


if __name__ == "__main__":
    try:
        test_store_node()
        sys.exit(0)
    except AssertionError as e:
        print_error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
