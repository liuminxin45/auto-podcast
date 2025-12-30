"""
Test script for AI Daily News fetcher integration
"""

import sys
from datetime import date

# Test 1: Import and registration
print("=" * 60)
print("Test 1: Import and Registration")
print("=" * 60)

try:
    from src.fetch import FetcherRegistry
    print("✓ FetcherRegistry imported successfully")
    
    registered_fetchers = FetcherRegistry.list_all()
    print(f"✓ Registered fetchers: {registered_fetchers}")
    
    if "ai_daily_news" in registered_fetchers:
        print("✓ ai_daily_news fetcher is registered")
    else:
        print("✗ ai_daily_news fetcher NOT registered")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Create instance
print("\n" + "=" * 60)
print("Test 2: Create Fetcher Instance")
print("=" * 60)

try:
    fetcher = FetcherRegistry.create_instance("ai_daily_news")
    if fetcher:
        print(f"✓ Fetcher instance created: {type(fetcher).__name__}")
        print(f"✓ Fetcher type: {fetcher.fetcher_type}")
    else:
        print("✗ Failed to create fetcher instance")
        sys.exit(1)
except Exception as e:
    print(f"✗ Instance creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Validate config
print("\n" + "=" * 60)
print("Test 3: Config Validation")
print("=" * 60)

test_config = {
    "name": "AI日报快讯",
    "fetcher": "ai_daily_news",
    "enabled": True,
    "category": "ai_tech",
    "urls": ["https://60s.viki.moe"]
}

try:
    is_valid = fetcher.validate_config(test_config)
    if is_valid:
        print("✓ Config validation passed")
    else:
        print("✗ Config validation failed")
        sys.exit(1)
except Exception as e:
    print(f"✗ Config validation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Fetch items (dry run - may fail if API is down, but should not crash)
print("\n" + "=" * 60)
print("Test 4: Fetch Items (API Call)")
print("=" * 60)

try:
    test_date = date.today()
    print(f"Testing fetch for date: {test_date}")
    
    result = fetcher.fetch_items(
        config=test_config,
        episode_date=test_date,
        timeout_seconds=10
    )
    
    print(f"✓ Fetch completed without crash")
    print(f"  Status: {result.status.value}")
    print(f"  Items count: {len(result.items)}")
    print(f"  Error message: {result.error_message}")
    
    if result.items:
        print(f"\n  Sample item:")
        sample = result.items[0]
        print(f"    - ID: {sample.get('id', 'N/A')}")
        print(f"    - Title: {sample.get('title', 'N/A')[:60]}...")
        print(f"    - URL: {sample.get('url', 'N/A')}")
        print(f"    - Source: {sample.get('source', 'N/A')}")
        print(f"    - Published: {sample.get('published_at', 'N/A')}")
    
except Exception as e:
    print(f"✗ Fetch failed with exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests completed successfully!")
print("=" * 60)
