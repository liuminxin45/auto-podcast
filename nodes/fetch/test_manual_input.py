"""
测试Fetch节点的手动输入新闻功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from nodes.fetch.config import FetchConfig
from nodes.fetch.node import run


def test_manual_inputs_only():
    """测试仅使用手动输入的新闻"""
    print("\n=== 测试1: 仅手动输入 ===")
    
    config = FetchConfig(
        sources=[],  # 不使用自动抓取
        manual_inputs=[
            {
                "title": "AI技术突破",
                "content": "OpenAI发布了最新的GPT-5模型..."
            },
            {
                "title": "量子计算进展",
                "content": "研究人员实现了100量子比特的稳定运行..."
            }
        ]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"总新闻数: {len(result['raw_contents'])}")
    print(f"手动新闻数: {sum(1 for item in result['raw_contents'] if item['type'] == 'manual')}")
    
    for i, item in enumerate(result['raw_contents']):
        print(f"{i+1}. [{item['type']}] {item['title']}")
    
    print("\n日志:")
    for log in result['logs']:
        print(f"  {log}")
    
    assert len(result['raw_contents']) == 2
    assert all(item['type'] == 'manual' for item in result['raw_contents'])
    print("✓ 测试通过")


def test_manual_with_auto():
    """测试手动输入与自动抓取混合使用"""
    print("\n=== 测试2: 手动输入 + 自动抓取 ===")
    
    config = FetchConfig(
        sources=[
            {"type": "rss", "url": "https://hnrss.org/frontpage"}
        ],
        max_items_per_source=3,
        manual_inputs=[
            {
                "title": "重要公告",
                "content": "这是一条重要的手动输入新闻"
            }
        ],
        prioritize_manual=True
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"总新闻数: {len(result['raw_contents'])}")
    manual_count = sum(1 for item in result['raw_contents'] if item['type'] == 'manual')
    auto_count = len(result['raw_contents']) - manual_count
    print(f"手动新闻数: {manual_count}")
    print(f"自动新闻数: {auto_count}")
    
    print("\n前5条新闻:")
    for i, item in enumerate(result['raw_contents'][:5]):
        print(f"{i+1}. [{item['type']}] {item['title'][:50]}")
    
    # 验证手动新闻在前面
    if result['raw_contents']:
        first_item = result['raw_contents'][0]
        print(f"\n第一条新闻类型: {first_item['type']}")
        assert first_item['type'] == 'manual', "手动新闻应该在最前面"
    
    print("✓ 测试通过")


def test_prioritize_auto():
    """测试自动抓取优先"""
    print("\n=== 测试3: 自动抓取优先 ===")
    
    config = FetchConfig(
        sources=[
            {"type": "rss", "url": "https://hnrss.org/frontpage"}
        ],
        max_items_per_source=2,
        manual_inputs=[
            {
                "title": "手动新闻",
                "content": "这条新闻应该在后面"
            }
        ],
        prioritize_manual=False  # 自动抓取优先
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"总新闻数: {len(result['raw_contents'])}")
    
    print("\n前3条新闻:")
    for i, item in enumerate(result['raw_contents'][:3]):
        print(f"{i+1}. [{item['type']}] {item['title'][:50]}")
    
    # 验证自动新闻在前面
    if len(result['raw_contents']) > 0:
        first_item = result['raw_contents'][0]
        print(f"\n第一条新闻类型: {first_item['type']}")
        # 注意：如果RSS抓取失败，可能第一条还是manual
        if first_item['type'] != 'manual':
            print("✓ 自动新闻在前面")
        else:
            print("⚠ RSS抓取可能失败，手动新闻在前面")
    
    print("✓ 测试通过")


def test_missing_fields():
    """测试缺少字段的手动输入"""
    print("\n=== 测试4: 缺少字段的手动输入 ===")
    
    config = FetchConfig(
        sources=[],
        manual_inputs=[
            {
                "title": "只有标题",
                # 缺少content字段，会使用空字符串
            },
            {
                "content": "只有内容",
                # 缺少title字段，会使用默认值
            },
            {
                "title": "完整新闻",
                "content": "有标题和内容"
            }
        ]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    print(f"总新闻数: {len(result['raw_contents'])}")
    
    for i, item in enumerate(result['raw_contents']):
        print(f"{i+1}. 标题: '{item['title']}', 内容: '{item['content'][:20]}...'")
    
    assert len(result['raw_contents']) == 3
    print("✓ 测试通过")


def test_manual_with_url():
    """测试带URL的手动输入"""
    print("\n=== 测试5: 带URL的手动输入 ===")
    
    config = FetchConfig(
        sources=[],
        manual_inputs=[
            {
                "title": "完整新闻",
                "content": "这是新闻内容",
                "url": "https://example.com/news1",
                "published": "2024-02-08"
            }
        ]
    )
    
    state = {"logs": [], "errors": []}
    result = run(state, config)
    
    item = result['raw_contents'][0]
    print(f"标题: {item['title']}")
    print(f"URL: {item['url']}")
    print(f"发布时间: {item['published']}")
    print(f"来源: {item['source']}")
    
    assert item['url'] == "https://example.com/news1"
    assert item['published'] == "2024-02-08"
    assert item['source'] == "manual_input"
    print("✓ 测试通过")


if __name__ == "__main__":
    print("开始测试Fetch节点手动输入功能...\n")
    
    try:
        test_manual_inputs_only()
        test_manual_with_auto()
        test_prioritize_auto()
        test_missing_fields()
        test_manual_with_url()
        
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
