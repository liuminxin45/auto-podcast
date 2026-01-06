"""
CLI Debug Tool

不经过 MCP，直接调用 domain/services 层进行调试。
用于开发和测试时快速验证功能。
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import sys

from src.domain.services.web_service import WebService
from src.adapters.search.bocha_ai_search_provider import BochaAISearchProvider
from src.adapters.fetch.http_fetcher import HttpFetcher
from src.adapters.fetch.html_extractor import HtmlExtractor


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("debug_web")


def create_web_service() -> WebService:
    """创建 WebService 实例"""
    import os
    search_provider = BochaAISearchProvider(
        api_key=os.environ.get("BOCHA_API_KEY"),
        timeout=30
    )
    fetcher = HttpFetcher(timeout=30)
    extractor = HtmlExtractor()
    
    return WebService(
        search_provider=search_provider,
        fetcher=fetcher,
        extractor=extractor,
        max_content_length=20000
    )


async def debug_search(query: str, max_results: int = 10):
    """调试搜索功能"""
    logger.info(f"开始搜索: query='{query}', max_results={max_results}")
    
    web_service = create_web_service()
    
    try:
        results = await web_service.search(query=query, max_results=max_results)
        
        print(f"\n搜索成功！返回 {len(results)} 条结果：\n")
        
        for i, result in enumerate(results, 1):
            print(f"[{i}] {result.title}")
            print(f"    URL: {result.url}")
            print(f"    摘要: {result.snippet[:100]}...")
            if result.source:
                print(f"    来源: {result.source}")
            if result.score:
                print(f"    评分: {result.score:.2f}")
            print()
        
        # 输出 JSON
        print("\n完整 JSON 输出：")
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
        
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        sys.exit(1)


async def debug_fetch(url: str, extract: bool = True):
    """调试抓取功能"""
    logger.info(f"开始抓取: url='{url}', extract={extract}")
    
    web_service = create_web_service()
    
    try:
        result = await web_service.fetch(url=url, extract_content=extract)
        
        print(f"\n抓取成功！\n")
        print(f"URL: {result.url}")
        print(f"标题: {result.title}")
        print(f"状态码: {result.status_code}")
        print(f"内容长度: {result.content_length} 字符")
        print(f"是否截断: {result.is_truncated}")
        
        if result.author:
            print(f"作者: {result.author}")
        if result.publish_date:
            print(f"发布日期: {result.publish_date}")
        
        print(f"\n内容预览（前 500 字符）：")
        print("-" * 80)
        print(result.content[:500])
        print("-" * 80)
        
        # 输出 JSON
        print("\n完整 JSON 输出：")
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        
    except Exception as e:
        logger.error(f"抓取失败: {e}", exc_info=True)
        sys.exit(1)


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="Web Service 调试工具（不经过 MCP）"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="最大返回结果数（默认 10）"
    )
    
    # fetch 命令
    fetch_parser = subparsers.add_parser("fetch", help="抓取网页")
    fetch_parser.add_argument("url", help="目标 URL")
    fetch_parser.add_argument(
        "--no-extract",
        action="store_true",
        help="不提取正文，只返回原始 HTML"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    if args.command == "search":
        asyncio.run(debug_search(args.query, args.max_results))
    elif args.command == "fetch":
        asyncio.run(debug_fetch(args.url, not args.no_extract))


if __name__ == "__main__":
    main()
