"""
MCP Server Layer - FastMCP Server

MCP Server 入口，只负责：
1. 协议接入（fastmcp）
2. 工具注册
3. 错误边界
4. 日志记录

不包含任何业务逻辑。
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Dict

from fastmcp import FastMCP

from src.mcp_server.router import Router
from src.mcp_server.dto import ExecRequest
from src.domain.services.web_service import WebService
from src.adapters.search.bocha_ai_search_provider import BochaAISearchProvider
from src.adapters.fetch.http_fetcher import HttpFetcher
from src.adapters.fetch.html_extractor import HtmlExtractor


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger("mcp_server")

# 创建 MCP 应用
mcp = FastMCP("auto-podcast-mcp")

# 全局变量
_router: Router | None = None
_start_time: float = time.time()
_version = "1.0.0"


def _get_router() -> Router:
    """获取路由器实例（延迟初始化）"""
    global _router
    
    if _router is None:
        logger.info("初始化 MCP Server 组件...")
        
        # 创建 adapters
        # 使用博查 AI Search API（需要配置 BOCHA_API_KEY 环境变量）
        import os
        search_provider = BochaAISearchProvider(
            api_key=os.environ.get("BOCHA_API_KEY"),
            timeout=30
        )
        fetcher = HttpFetcher(timeout=30)
        extractor = HtmlExtractor()
        
        # 创建 service
        web_service = WebService(
            search_provider=search_provider,
            fetcher=fetcher,
            extractor=extractor,
            max_content_length=20000
        )
        
        # 创建 router
        _router = Router(web_service=web_service)
        
        logger.info("MCP Server 初始化完成")
    
    return _router


@mcp.tool()
async def exec(op: str, payload: dict) -> dict:
    """
    统一执行入口
    
    Args:
        op: 操作类型（如 'web.search', 'web.fetch'）
        payload: 操作参数
        
    Returns:
        操作结果，格式：
        - 成功: {"ok": true, "data": {...}, "meta": {...}}
        - 失败: {"ok": false, "error": {"code": "...", "message": "...", "detail": ...}, "meta": {...}}
    """
    request_id = f"{int(time.time() * 1000)}"
    start_time = time.time()
    
    logger.info(f"[{request_id}] exec: op={op}, payload_keys={list(payload.keys())}")
    
    try:
        # 获取路由器
        router = _get_router()
        
        # 执行操作
        result = await router.route(op, payload)
        
        # 添加元数据
        result.meta.update({
            "request_id": request_id,
            "duration_ms": int((time.time() - start_time) * 1000),
        })
        
        # 转换为字典
        response = result.to_dict()
        
        if result.ok:
            logger.info(f"[{request_id}] 成功: op={op}, duration={result.meta['duration_ms']}ms")
        else:
            error_code = result.error.code if result.error else "UNKNOWN"
            error_msg = result.error.message if result.error else "未知错误"
            logger.warning(
                f"[{request_id}] 失败: op={op}, error={error_code}, "
                f"message={error_msg}"
            )
        
        return response
    
    except Exception as e:
        # 捕获所有未处理的异常，避免 server 崩溃
        logger.error(f"[{request_id}] 未捕获的异常: {e}", exc_info=True)
        
        return {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"内部错误: {str(e)}",
                "detail": str(e)
            },
            "meta": {
                "request_id": request_id,
                "duration_ms": int((time.time() - start_time) * 1000),
            }
        }


@mcp.tool()
def health() -> dict:
    """
    健康检查
    
    Returns:
        服务器状态信息
    """
    router = _get_router()
    
    return {
        "version": _version,
        "uptime_seconds": time.time() - _start_time,
        "available_ops": router.get_supported_ops(),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        }
    }


@mcp.tool()
def schema() -> dict:
    """
    获取操作 schema
    
    Returns:
        所有支持的操作及其参数定义
    """
    router = _get_router()
    
    return {
        "ops": router.get_op_schema()
    }


def main():
    """启动 MCP Server（stdio 模式）"""
    logger.info(f"启动 MCP Server v{_version}...")
    logger.info("传输模式: stdio")
    logger.info("等待 MCP Client 连接...")
    
    # 运行 MCP Server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
