"""
Tests for Router

测试 MCP Server 层的路由逻辑。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.mcp_server.router import Router
from src.domain.models import SearchResult, FetchResult


@pytest.fixture
def mock_web_service():
    """Mock WebService"""
    service = AsyncMock()
    service.search_provider.get_provider_name.return_value = "mock"
    return service


@pytest.fixture
def router(mock_web_service):
    """创建 Router 实例"""
    return Router(web_service=mock_web_service)


class TestRouter:
    """测试路由器"""
    
    @pytest.mark.asyncio
    async def test_route_web_search_success(self, router, mock_web_service):
        """测试 web.search 路由成功"""
        # 准备 mock 数据
        mock_result = SearchResult(
            title="测试",
            snippet="摘要",
            url="https://example.com"
        )
        mock_web_service.search.return_value = [mock_result]
        
        # 执行路由
        result = await router.route("web.search", {"query": "测试", "max_results": 5})
        
        # 验证结果
        assert result.ok is True
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        assert result.meta["count"] == 1
        
        # 验证调用
        mock_web_service.search.assert_called_once_with(
            query="测试",
            max_results=5
        )
    
    @pytest.mark.asyncio
    async def test_route_web_fetch_success(self, router, mock_web_service):
        """测试 web.fetch 路由成功"""
        # 准备 mock 数据
        mock_result = FetchResult(
            url="https://example.com",
            title="测试标题",
            content="测试内容",
            status_code=200,
            content_length=100
        )
        mock_web_service.fetch.return_value = mock_result
        
        # 执行路由
        result = await router.route("web.fetch", {"url": "https://example.com"})
        
        # 验证结果
        assert result.ok is True
        assert isinstance(result.data, dict)
        assert result.data["title"] == "测试标题"
        
        # 验证调用
        mock_web_service.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_route_unsupported_op(self, router):
        """测试不支持的操作"""
        result = await router.route("invalid.op", {})
        
        assert result.ok is False
        assert result.error.code == "UNSUPPORTED_OP"
    
    @pytest.mark.asyncio
    async def test_route_missing_query(self, router):
        """测试缺少必填参数"""
        result = await router.route("web.search", {})
        
        assert result.ok is False
        assert result.error.code == "MISSING_QUERY"
    
    @pytest.mark.asyncio
    async def test_route_invalid_query_type(self, router):
        """测试参数类型错误"""
        result = await router.route("web.search", {"query": 123})
        
        assert result.ok is False
        assert result.error.code == "INVALID_QUERY_TYPE"
    
    def test_get_supported_ops(self, router):
        """测试获取支持的操作列表"""
        ops = router.get_supported_ops()
        
        assert "web.search" in ops
        assert "web.fetch" in ops
    
    def test_get_op_schema(self, router):
        """测试获取操作 schema"""
        schema = router.get_op_schema()
        
        assert "web.search" in schema
        assert "web.fetch" in schema
        assert "parameters" in schema["web.search"]
        assert "returns" in schema["web.search"]
