# MCP Server 集成文档

## 概述

本项目集成了一个高度隔离、分层架构的 MCP Server，用于提供 Web 搜索和网页抓取能力。

### 架构特点

- **严格分层**：Domain、Adapters、Services、MCP Server 四层架构
- **高度隔离**：fastmcp 仅在 MCP Server 层使用，不渗透到业务层
- **可测试性**：每层都可独立测试和调试
- **可扩展性**：通过接口抽象，易于替换实现

## 项目结构

```
src/
├── domain/                    # 领域层（抽象接口和模型）
│   ├── interfaces.py         # SearchProvider, Fetcher, Extractor 接口
│   ├── models.py             # SearchResult, FetchResult, ErrorDetail 等
│   └── services/
│       └── web_service.py    # 纯业务逻辑（搜索、抓取、裁剪）
├── adapters/                  # 适配器层（外部依赖）
│   ├── search/
│   │   ├── base.py           # SearchProvider 基类
│   │   ├── mock_provider.py  # Mock 搜索提供商（默认）
│   │   └── bocha_provider.py # 博查搜索提供商（待实现）
│   └── fetch/
│       ├── http_fetcher.py   # httpx 抓取器
│       └── html_extractor.py # BeautifulSoup 内容提取
├── mcp_server/                # MCP Server 层（协议接入）
│   ├── server.py             # fastmcp 入口
│   ├── router.py             # op 路由和参数校验
│   └── dto.py                # 输入输出 DTO
└── cli/
    └── debug_web.py          # CLI 调试工具（不经过 MCP）

tests/
├── test_web_service.py       # WebService 单元测试
└── test_router.py            # Router 单元测试
```

## 安装依赖

```bash
pip install -r requirements.txt
```

主要新增依赖：
- `fastmcp>=0.2.0` - MCP Server 框架
- `httpx>=0.27.0` - 异步 HTTP 客户端
- `pytest>=8.0.0` - 测试框架
- `pytest-asyncio>=0.23.0` - 异步测试支持

## 使用方式

### 1. 启动 MCP Server（stdio 模式）

```bash
python -m src.mcp_server.server
```

MCP Server 将以 stdio 模式启动，等待 MCP Client 连接。

### 2. CLI 调试（不经过 MCP）

#### 搜索功能

```bash
# 基本搜索
python -m src.cli.debug_web search "Python 教程"

# 指定返回结果数
python -m src.cli.debug_web search "机器学习" --max-results 5
```

#### 抓取功能

```bash
# 抓取并提取正文
python -m src.cli.debug_web fetch "https://example.com"

# 只抓取 HTML，不提取正文
python -m src.cli.debug_web fetch "https://example.com" --no-extract
```

### 3. 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_web_service.py

# 查看详细输出
pytest tests/ -v

# 查看覆盖率
pytest tests/ --cov=src
```

## MCP 工具说明

### 1. `exec(op: str, payload: dict)`

统一执行入口，通过 `op` 参数指定操作类型。

#### 支持的操作

**web.search** - 网络搜索

```json
{
  "op": "web.search",
  "payload": {
    "query": "搜索关键词",
    "max_results": 10
  }
}
```

返回格式：
```json
{
  "ok": true,
  "data": [
    {
      "title": "标题",
      "snippet": "摘要",
      "url": "https://...",
      "source": "来源",
      "published_date": "2026-01-06",
      "score": 0.9
    }
  ],
  "meta": {
    "count": 1,
    "provider": "mock",
    "request_id": "...",
    "duration_ms": 123
  }
}
```

**web.fetch** - 抓取网页

```json
{
  "op": "web.fetch",
  "payload": {
    "url": "https://example.com",
    "extract_content": true,
    "timeout": 30
  }
}
```

返回格式：
```json
{
  "ok": true,
  "data": {
    "url": "https://example.com",
    "title": "页面标题",
    "content": "正文内容...",
    "author": "作者",
    "publish_date": "2026-01-06",
    "status_code": 200,
    "content_length": 1234,
    "is_truncated": false
  },
  "meta": {
    "url": "https://example.com",
    "content_length": 1234,
    "is_truncated": false,
    "request_id": "...",
    "duration_ms": 456
  }
}
```

错误格式：
```json
{
  "ok": false,
  "error": {
    "code": "INVALID_QUERY",
    "message": "查询不能为空",
    "detail": null
  },
  "meta": {
    "request_id": "...",
    "duration_ms": 12
  }
}
```

### 2. `health()`

健康检查，返回服务器状态。

```json
{
  "version": "1.0.0",
  "uptime_seconds": 123.45,
  "available_ops": ["web.search", "web.fetch"],
  "environment": {
    "python_version": "3.11.0",
    "platform": "win32"
  }
}
```

### 3. `schema()`

获取操作的参数定义（用于 LLM/Client 自描述调用）。

```json
{
  "ops": {
    "web.search": {
      "description": "执行网络搜索",
      "parameters": {
        "query": {
          "type": "string",
          "required": true,
          "description": "搜索查询"
        },
        "max_results": {
          "type": "integer",
          "required": false,
          "default": 10,
          "description": "最大返回结果数（1-50）"
        }
      },
      "returns": { ... }
    },
    "web.fetch": { ... }
  }
}
```

## 搜索提供商配置

**当前默认使用博查 AI Search API**，这是博查提供的强大搜索服务，支持：
- ✅ **网页搜索**：返回最多 50 条网页结果，含标题、摘要、URL
- ✅ **图片搜索**：返回相关图片
- ✅ **模态卡**：天气、百科、医疗、股票、汇率等结构化信息
- ✅ **AI 答案**：可选的大模型生成答案（需开启）

#### API Key 配置（必需）

博查 AI Search 需要 API Key，请通过环境变量配置：

```bash
export BOCHA_API_KEY="<api-key>"
```

或在代码中传入：

```python
# src/mcp_server/server.py
search_provider = BochaAISearchProvider(
    api_key="<api-key>",
    timeout=30
)
```

#### 搜索参数

博查 AI Search 支持以下参数：

- `query`：搜索查询（必需）
- `count`：返回结果数量（1-50，默认 10）
- `freshness`：时间范围
  - `oneDay`：一天内
  - `oneWeek`：一周内
  - `oneMonth`：一个月内
  - `oneYear`：一年内
  - `noLimit`：不限（默认）
- `include_answer`：是否包含 AI 生成的答案（默认 false）

#### 返回结果类型

1. **网页结果**：标题、摘要、URL、来源、发布时间
2. **模态卡**：
   - 天气卡（国内/国际）
   - 百科卡（专业版）
   - 医疗卡（普通版/专业版）
   - 万年历、火车时刻表
   - 星座属相、贵金属、汇率、油价
   - 手机参数、股票、汽车信息

### 实现新的搜索提供商

1. 在 `src/adapters/search/` 下创建新文件（如 `tavily_provider.py`）
2. 继承 `BaseSearchProvider`，实现 `search()` 和 `get_provider_name()` 方法
3. 在 `server.py` 中替换 `search_provider`

示例：

```python
from src.adapters.search.base import BaseSearchProvider

class TavilySearchProvider(BaseSearchProvider):
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
    
    async def search(self, query: str, max_results: int = 10, **kwargs):
        # 调用 Tavily API
        # 返回归一化的结果列表
        pass
    
    def get_provider_name(self) -> str:
        return "tavily"
```

## 配置说明

### 环境变量（可选）

```bash
# 博查 API Key（如果使用博查搜索）
export BOCHA_API_KEY="your-api-key"

# 日志级别
export LOG_LEVEL="INFO"
```

### 代码配置

在 `src/mcp_server/server.py` 的 `_get_router()` 函数中修改：

```python
# 最大内容长度（字符数）
web_service = WebService(
    search_provider=search_provider,
    fetcher=fetcher,
    extractor=extractor,
    max_content_length=20000  # 修改此处
)

# HTTP 超时时间
fetcher = HttpFetcher(timeout=30)  # 修改此处
```

## 开发指南

### 添加新操作

1. 在 `src/domain/services/web_service.py` 中添加业务方法
2. 在 `src/mcp_server/router.py` 中：
   - 添加 op 到 `SUPPORTED_OPS`
   - 添加路由处理函数 `_handle_xxx()`
   - 更新 `get_op_schema()` 添加 schema
3. 编写测试

### 调试技巧

1. **使用 CLI 调试**：不经过 MCP，直接测试业务逻辑
   ```bash
   python -m src.cli.debug_web search "测试"
   ```

2. **查看日志**：MCP Server 日志输出到 stderr
   ```bash
   python -m src.mcp_server.server 2> server.log
   ```

3. **单元测试**：隔离测试各层
   ```bash
   pytest tests/test_web_service.py -v
   ```

4. **Mock 外部依赖**：使用 `MockSearchProvider` 避免真实 API 调用

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| `INVALID_OP` | op 参数为空 |
| `UNSUPPORTED_OP` | 不支持的操作类型 |
| `MISSING_QUERY` | 缺少必填参数 query |
| `INVALID_QUERY_TYPE` | query 参数类型错误 |
| `EMPTY_QUERY` | 查询为空字符串 |
| `QUERY_TOO_LONG` | 查询超过最大长度 |
| `INVALID_URL` | URL 格式错误 |
| `HTTP_ERROR` | HTTP 请求失败 |
| `TIMEOUT` | 请求超时 |
| `NETWORK_ERROR` | 网络错误 |
| `PARSE_ERROR` | HTML 解析失败 |
| `INTERNAL_ERROR` | 内部错误 |

## 性能优化建议

1. **内容长度限制**：默认 20000 字符，可根据需求调整
2. **超时设置**：HTTP 请求默认 30 秒，可根据网络情况调整
3. **并发控制**：如需批量操作，在业务层实现并发控制
4. **缓存策略**：可在 `WebService` 中添加缓存逻辑

## 故障排查

### MCP Server 无法启动

1. 检查依赖是否安装：`pip list | grep fastmcp`
2. 检查 Python 版本：`python --version`（需要 3.8+）
3. 查看错误日志

### 搜索返回空结果

1. 确认使用的是 `MockSearchProvider`（默认返回假数据）
2. 如使用真实 API，检查 API Key 是否配置
3. 查看日志中的 API 调用详情

### 抓取失败

1. 检查 URL 是否可访问
2. 检查网络连接
3. 增加超时时间
4. 查看详细错误信息

## 许可证

本 MCP Server 集成遵循项目整体许可证。

## 联系方式

如有问题或建议，请联系 Auto-Podcast Team。
