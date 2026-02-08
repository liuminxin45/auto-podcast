"""
测试新的fetch节点流程
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from nodes.fetch.config import FetchConfig
from nodes.fetch.node import run, get_available_sources


def test_get_available_sources():
    """测试获取可用数据源列表"""
    print("\n=== 测试1: 获取可用数据源 ===")
    
    sources = get_available_sources()
    print(f"找到 {len(sources)} 个数据源:")
    for source in sources:
        print(f"  - {source['id']}: {source['name']}")
        print(f"    {source['description']}")
    
    assert len(sources) >= 3, "应该至少有3个数据源"
    print("✓ 测试通过")


def test_fetch_single_source():
    """测试单个数据源"""
    print("\n=== 测试2: 单个数据源 (hackernews) ===")
    
    config = FetchConfig(
        enabled_sources=["hackernews"]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"抓取到 {len(result['raw_contents'])} 条新闻")
    
    if result['raw_contents']:
        print("\n前3条新闻:")
        for i, item in enumerate(result['raw_contents'][:3]):
            print(f"{i+1}. {item['title'][:60]}")
            print(f"   来源: {item['source']}")
    
    print("\n日志:")
    for log in result['logs']:
        print(f"  {log}")
    
    assert len(result['raw_contents']) > 0, "应该抓取到新闻"
    print("✓ 测试通过")


def test_fetch_multiple_sources():
    """测试多个数据源"""
    print("\n=== 测试3: 多个数据源 ===")
    
    config = FetchConfig(
        enabled_sources=["hackernews", "example_custom"]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"总共抓取到 {len(result['raw_contents'])} 条新闻")
    
    # 统计各个来源的数量
    sources_count = {}
    for item in result['raw_contents']:
        source = item['source']
        sources_count[source] = sources_count.get(source, 0) + 1
    
    print("\n各来源统计:")
    for source, count in sources_count.items():
        print(f"  {source}: {count} 条")
    
    print("\n日志:")
    for log in result['logs']:
        print(f"  {log}")
    
    assert len(result['raw_contents']) > 0, "应该抓取到新闻"
    assert len(sources_count) >= 2, "应该有至少2个不同的来源"
    print("✓ 测试通过")


def test_fetch_no_sources():
    """测试不启用任何数据源"""
    print("\n=== 测试4: 不启用数据源 ===")
    
    config = FetchConfig(
        enabled_sources=[]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"抓取到 {len(result['raw_contents'])} 条新闻")
    
    assert len(result['raw_contents']) == 0, "不应该抓取到新闻"
    print("✓ 测试通过")


def test_fetch_invalid_source():
    """测试无效的数据源"""
    print("\n=== 测试5: 无效的数据源 ===")
    
    config = FetchConfig(
        enabled_sources=["nonexistent_source", "hackernews"]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"抓取到 {len(result['raw_contents'])} 条新闻")
    
    print("\n日志:")
    for log in result['logs']:
        print(f"  {log}")
    
    # 应该跳过无效源，但仍能从有效源抓取
    assert len(result['raw_contents']) > 0, "应该从有效源抓取到新闻"
    assert any("not found" in log for log in result['logs']), "应该有警告日志"
    print("✓ 测试通过")


if __name__ == "__main__":
    print("开始测试新的Fetch节点流程...\n")
    
    try:
        test_get_available_sources()
        test_fetch_single_source()
        test_fetch_multiple_sources()
        test_fetch_no_sources()
        test_fetch_invalid_source()
        
        print("\n" + "="*50)
        print("✓ 所有测试通过！")
        print("="*50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
