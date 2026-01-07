"""
MCP Client for Research

通过 MCP Server 调用 AI Search API 进行研究
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("research.sources.mcp")


def mcp_search_items(
    items: List[Dict[str, Any]],
    max_results: int = 10,
    timeout_seconds: int = 60,
    save_dir: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    通过 MCP Server 执行搜索
    
    Args:
        items: 要搜索的条目列表
        max_results: 最大返回结果数
        timeout_seconds: 超时时间（秒）
        save_dir: 保存请求/响应报文的目录
        
    Returns:
        搜索结果字典
    """
    if not items:
        logger.error("items 列表为空")
        return None
    
    # 提取查询文本
    queries = []
    for item in items:
        if isinstance(item, dict):
            query = item.get("title") or item.get("text") or item.get("content", "")
        else:
            query = str(item)
        
        if query:
            queries.append(query.strip())
    
    if not queries:
        logger.error("无法从 items 中提取查询")
        return None
    
    # 合并查询
    combined_query = " ".join(queries[:3])  # 只取前3个查询避免过长
    
    logger.info(f"开始 MCP 搜索，查询: {combined_query[:100]}...")
    
    start_time = time.perf_counter()
    
    # 预先计算保存路径和查询哈希
    save_path: Optional[Path] = None
    query_hash = str(hash(combined_query))[:8]
    
    if save_dir:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # 构建 MCP 请求
        mcp_request = {
            "op": "web.search",
            "payload": {
                "query": combined_query,
                "max_results": max_results
            }
        }
        
        # 保存请求报文
        if save_path:
            request_file = save_path / f"mcp_request_{query_hash}.json"
            with open(request_file, "w", encoding="utf-8") as f:
                json.dump(mcp_request, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存请求报文: {request_file}")
        
        # 调用 MCP Server（通过 CLI 工具模拟）
        # 实际应该通过 stdio 或其他 MCP 协议调用
        result = _call_mcp_server(mcp_request, timeout_seconds)
        
        # 保存响应报文
        if save_path and result:
            response_file = save_path / f"mcp_response_{query_hash}.json"
            with open(response_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存响应报文: {response_file}")
        
        if not result or not result.get("ok"):
            error_msg = result.get("error", {}).get("message") if result else "未知错误"
            logger.error(f"MCP 搜索失败: {error_msg}")
            return None
        
        # 转换为统一格式
        search_results = result.get("data", [])
        logger.info(f"MCP 搜索成功，返回 {len(search_results)} 条结果")
        
        # 构建返回格式（兼容现有 research 流程）
        response_text = _format_search_results(search_results)
        
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"研究完成，耗时 {processing_time_ms}ms")
        
        return {
            "ok": True,
            "response_json": {
                "choices": [{
                    "message": {
                        "content": response_text
                    }
                }]
            },
            "response_text": response_text,
            "model": "mcp-ai-search",
            "metadata": {
                "total_results": len(search_results),
                "query": combined_query,
                "provider": "mcp",
                "processing_time_ms": processing_time_ms
            }
        }
    
    except Exception as e:
        logger.error(f"MCP 搜索异常: {e}", exc_info=True)
        return None


def _call_mcp_server(request: Dict[str, Any], timeout: int) -> Optional[Dict[str, Any]]:
    """
    调用 MCP Server
    
    这里使用简化的实现，直接调用 WebService
    实际生产环境应该通过 MCP 协议（stdio/HTTP）调用
    """
    try:
        # 导入 WebService 和适配器
        import os
        from src.domain.services.web_service import WebService
        from src.adapters.search.bocha_ai_search_provider import BochaAISearchProvider
        from src.adapters.fetch.http_fetcher import HttpFetcher
        from src.adapters.fetch.html_extractor import HtmlExtractor
        import asyncio
        
        # 创建服务实例
        search_provider = BochaAISearchProvider(
            api_key=os.environ.get("BOCHA_API_KEY"),
            timeout=timeout
        )
        fetcher = HttpFetcher(timeout=timeout)
        extractor = HtmlExtractor()
        
        web_service = WebService(
            search_provider=search_provider,
            fetcher=fetcher,
            extractor=extractor
        )
        
        # 执行搜索
        op = request.get("op")
        payload = request.get("payload", {})
        
        if op == "web.search":
            query = payload.get("query")
            max_results = payload.get("max_results", 10)
            
            # 运行异步搜索
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    web_service.search(query=query, max_results=max_results)
                )
                
                # 转换为字典格式
                data = [r.to_dict() for r in results]
                
                return {
                    "ok": True,
                    "data": data,
                    "meta": {
                        "count": len(results),
                        "provider": "bocha-ai-search"
                    }
                }
            finally:
                loop.close()
        else:
            logger.error(f"不支持的操作: {op}")
            return None
    
    except Exception as e:
        logger.error(f"调用 MCP Server 失败: {e}", exc_info=True)
        return {
            "ok": False,
            "error": {
                "code": "MCP_ERROR",
                "message": str(e)
            }
        }


def _format_search_results(results: List[Dict[str, Any]]) -> str:
    """
    格式化搜索结果为文本
    
    Args:
        results: 搜索结果列表
        
    Returns:
        格式化的文本
    """
    if not results:
        return "未找到相关结果"
    
    lines = []
    for idx, result in enumerate(results, 1):
        title = result.get("title", "无标题")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        source = result.get("source", "")
        
        lines.append(f"{idx}. {title}")
        if source:
            lines.append(f"   来源: {source}")
        if snippet:
            lines.append(f"   摘要: {snippet[:200]}")
        if url:
            lines.append(f"   链接: {url}")
        lines.append("")
    
    return "\n".join(lines)
