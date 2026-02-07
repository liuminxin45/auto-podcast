#!/usr/bin/env python
"""
Integration Test Script

Tests the complete workflow execution with mock data.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from protocol.state import PodcastState
from nodes.fetch.node import run as fetch_run
from nodes.fetch.config import FetchConfig
from nodes.preprocess.node import run as preprocess_run
from nodes.preprocess.config import PreprocessConfig


def test_fetch_to_preprocess_pipeline():
    """Test basic pipeline: fetch -> preprocess"""
    print("=" * 60)
    print("Integration Test: Fetch -> Preprocess")
    print("=" * 60)
    
    # Initialize state
    state = PodcastState().to_dict()
    
    # Configure fetch with mock data
    fetch_config = FetchConfig(
        sources=[],
        max_items_per_source=5
    )
    
    # Inject mock data directly (since we can't fetch real data in tests)
    state['raw_contents'] = [
        {
            'title': 'Test Article 1',
            'content': 'This is a test article with enough content to pass validation. ' * 10,
            'url': 'https://example.com/1',
            'source': 'test'
        },
        {
            'title': 'Test Article 2',
            'content': 'Another test article with sufficient length for processing. ' * 10,
            'url': 'https://example.com/2',
            'source': 'test'
        },
        {
            'title': 'Short',
            'content': 'Too short',
            'url': 'https://example.com/3',
            'source': 'test'
        }
    ]
    
    print(f"✓ Initial state created with {len(state['raw_contents'])} mock items")
    
    # Run preprocess
    preprocess_config = PreprocessConfig(
        min_content_length=50,
        max_content_length=10000,
        remove_duplicates=True
    )
    
    state = preprocess_run(state, preprocess_config)
    
    print(f"✓ Preprocess completed")
    print(f"  - Input: {len(state.get('raw_contents', []))} items")
    print(f"  - Output: {len(state.get('cleaned_contents', []))} items")
    print(f"  - Logs: {len(state.get('logs', []))} entries")
    print(f"  - Errors: {len(state.get('errors', []))} errors")
    
    # Validate results
    assert len(state['cleaned_contents']) == 2, "Should filter out short content"
    assert len(state['errors']) == 0, "Should have no errors"
    assert len(state['logs']) > 0, "Should have log entries"
    
    print("\n✅ Integration test PASSED")
    return True


def test_state_serialization():
    """Test state serialization/deserialization"""
    print("\n" + "=" * 60)
    print("Test: State Serialization")
    print("=" * 60)
    
    # Create state
    state = PodcastState()
    state.raw_contents = [{'test': 'data'}]
    state.logs.append("Test log")
    
    # Serialize
    json_str = state.to_json()
    state_dict = state.to_dict()
    
    # Deserialize
    restored = PodcastState.from_json(json_str)
    restored_dict = PodcastState.from_dict(state_dict)
    
    assert restored.episode_id == state.episode_id
    assert len(restored.raw_contents) == 1
    assert len(restored.logs) == 1
    
    print("✓ JSON serialization works")
    print("✓ Dict conversion works")
    print("\n✅ Serialization test PASSED")
    return True


def main():
    print("\n🧪 Running Integration Tests\n")
    
    tests = [
        ("Fetch->Preprocess Pipeline", test_fetch_to_preprocess_pipeline),
        ("State Serialization", test_state_serialization),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
