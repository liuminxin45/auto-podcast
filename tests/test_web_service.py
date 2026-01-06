"""
Tests for WebService

测试 domain/services 层的业务逻辑。
使用 mock adapters 进行隔离测试。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain.services.web_service import WebService
from src.domain.models import SearchResult, FetchResult, ValidationError, SearchError


@pytest.fixture
def mock_search_provider():
    """Mock 搜索提供商"""
    provider = AsyncMock()
    provider.get_provider_name.return_value = "mock"
    return provider


@pytest.fixture
def mock_fetcher():
    """Mock 抓取器"""
    return AsyncMock()


@pytest.fixture
def mock_extractor():
    """Mock 提取器"""
    return MagicMock()


@pytest.fixture
def web_service(mock_search_provider, mock_fetcher, mock_extractor):
    """创建 WebService 实例"""
    return WebService(
        search_provider=mock_search_provider,
        fetcher=mock_fetcher,
        extractor=mock_extractor,
        max_content_length=1000
    )


class TestWebServiceSearch:
    """测试搜索功能"""
    
    @pytest.mark.asyncio
    async def test_search_success(self, web_service, mock_search_provider):
        """测试搜索成功"""
        # 准备 mock 数据
        mock_search_provider.search.return_value = [
            {
                "title": "测试标题",
                "snippet": "测试摘要",
                "url": "https://example.com",
                "source": "测试来源",
                "score": 0.9
            }
        ]
        
        # 执行搜索
        results = await web_service.search("测试查询", max_results=10)
        
        # 验证结果
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "测试标题"
        assert results[0].url == "https://example.com"
        
        # 验证调用
        mock_search_provider.search.assert_called_once_with(
            query="测试查询",
            max_results=10
        )
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, web_service):
        """测试空查询"""
        with pytest.raises(ValidationError) as exc_info:
            await web_service.search("", max_results=10)
        
        assert exc_info.value.code == "EMPTY_QUERY"
    
    @pytest.mark.asyncio
    async def test_search_invalid_max_results(self, web_service):
        """测试无效的 max_results"""
        with pytest.raises(ValidationError) as exc_info:
            await web_service.search("测试", max_results=100)
        
        assert exc_info.value.code == "INVALID_MAX_RESULTS"


class TestWebServiceFetch:
    """测试抓取功能"""
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, web_service, mock_fetcher, mock_extractor):
        """测试抓取成功"""
        # 准备 mock 数据
        mock_fetcher.fetch.return_value = {
            "content": "<html><body>测试内容</body></html>",
            "status_code": 200
        }
        
        mock_extractor.extract.return_value = {
            "title": "测试标题",
            "content": "测试正文内容",
            "author": "测试作者",
            "publish_date": "2026-01-06"
        }
        
        # 执行抓取
        result = await web_service.fetch("https://example.com")
        
        # 验证结果
        assert isinstance(result, FetchResult)
        assert result.title == "测试标题"
        assert result.content == "测试正文内容"
        assert result.author == "测试作者"
        assert result.status_code == 200
        
        # 验证调用
        mock_fetcher.fetch.assert_called_once()
        mock_extractor.extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_content_truncation(self, web_service, mock_fetcher, mock_extractor):
        """测试内容截断"""
        # 准备超长内容
        long_content = "x" * 2000
        
        mock_fetcher.fetch.return_value = {
            "content": "<html><body>测试</body></html>",
            "status_code": 200
        }
        
        mock_extractor.extract.return_value = {
            "title": "测试",
            "content": long_content,
        }
        
        # 执行抓取（max_content_length=1000）
        result = await web_service.fetch("https://example.com")
        
        # 验证截断
        assert len(result.content) == 1000
        assert result.is_truncated is True
    
    @pytest.mark.asyncio
    async def test_fetch_empty_url(self, web_service):
        """测试空 URL"""
        with pytest.raises(ValidationError) as exc_info:
            await web_service.fetch("")
        
        assert exc_info.value.code == "EMPTY_URL"
    
    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self, web_service):
        """测试无效 URL"""
        with pytest.raises(ValidationError) as exc_info:
            await web_service.fetch("not-a-url")
        
        assert exc_info.value.code == "INVALID_URL"
