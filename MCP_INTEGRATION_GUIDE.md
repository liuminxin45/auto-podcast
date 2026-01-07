# MCP Server + AI Search API 集成指南

## 概述

现在你的 Research 流程已经集成了 **MCP Server + 博查 AI Search API**，提供更强大的搜索能力。

## 重要概念澄清

### Provider vs Protocol

- **Provider（数据提供商）**：指数据来源，如 `metaso`、`anspire`、`bocha`
- **MCP（协议层）**：指通信方式，不是数据提供商

**正确的配置方式**：
```yaml
research:
  provider: "bocha"         # 数据提供商
  use_mcp_server: true      # 是否通过 MCP Server 调用（协议层）
```

**❌ 错误的配置方式**：
```yaml
research:
  provider: "mcp"  # MCP 不是数据提供商！
```

## 架构变化

### 之前的架构
```
Research 流程 → 博查 Web Search API (直接 HTTP 调用)
                ↓
            网页搜索结果
```

### 现在的架构（use_mcp_server: true）
```
Research 流程 → MCP Client → MCP Server → 博查 AI Search API
                              ↓
                    网页 + 模态卡 + AI答案
```

### 或者直接调用（use_mcp_server: false）
```
Research 流程 → 博查 Web/AI Search API (直接 HTTP 调用)
                ↓
            搜索结果
```

## 主要优势

| 特性 | Web Search API | AI Search API (MCP) |
|------|---------------|---------------------|
| 搜索结果 | 仅网页 | 网页 + 模态卡 + AI答案 |
| 结构化数据 | 无 | 12种模态卡（天气、股票等） |
| 日志追踪 | 基础 | 完整的多层日志 |
| 接口标准化 | 直接调用 | MCP 标准协议 |
| 错误处理 | 基础 | 完整的错误边界 |

## 配置说明

### 1. 配置文件 (`config/base/settings.yaml`)

```yaml
research:
  provider: "bocha"         # 数据提供商
  use_mcp_server: true      # 通过 MCP Server 调用
  enabled: true
  timeout_seconds: 60
  max_items: 10
  
  # Bocha 配置
  bocha:
    api_key: "your-api-key"
    api_type: "ai-search"   # web-search | ai-search
    count: 10
    summary: true
    freshness: "noLimit"
```

### 配置选项说明

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `provider` | 数据提供商 | `metaso`, `anspire`, `bocha` |
| `use_mcp_server` | 是否通过 MCP Server 调用 | `true`, `false` |
| `bocha.api_type` | 博查 API 类型 | `web-search`, `ai-search` |

### 不同配置的效果

#### 配置 1：MCP Server + AI Search（推荐）
```yaml
provider: "bocha"
use_mcp_server: true
bocha:
  api_type: "ai-search"
```
→ 通过 MCP Server 调用博查 AI Search API，获得网页 + 模态卡 + AI答案

#### 配置 2：直接调用 AI Search
```yaml
provider: "bocha"
use_mcp_server: false
bocha:
  api_type: "ai-search"
```
→ 直接 HTTP 调用博查 AI Search API（需要实现）

#### 配置 3：直接调用 Web Search
```yaml
provider: "bocha"
use_mcp_server: false
bocha:
  api_type: "web-search"
```
→ 直接 HTTP 调用博查 Web Search API（当前实现）

### 2. 环境变量

确保设置了博查 API Key：

```bash
export BOCHA_API_KEY="<api-key>"
```

## 使用方法

### 运行完整流程

```bash
python run.py --step all
```

### 日志输出示例

```
research.sources.mcp - INFO - 开始 MCP 搜索，查询: BMX 推出 ByteSize 系列...
research.sources.mcp - INFO - 已保存请求报文: out/runs/.../mcp_request_xxx.json
research.sources.mcp - INFO - 已保存响应报文: out/runs/.../mcp_response_xxx.json
research.sources.mcp - INFO - MCP 搜索成功，返回 10 条结果
research.sources.mcp - INFO - 研究完成，耗时 1234ms
```

## 文件结构

```
src/
├── research/
│   └── sources/
│       ├── mcp_client.py          # 新增：MCP Client 适配器
│       └── research_client.py     # 更新：支持 MCP Provider
├── mcp_server/
│   ├── server.py                  # MCP Server 入口
│   ├── router.py                  # 路由层
│   └── dto.py                     # 数据传输对象
├── domain/
│   ├── services/
│   │   └── web_service.py         # 业务服务层
│   ├── interfaces.py              # 抽象接口
│   └── models.py                  # 领域模型
└── adapters/
    ├── search/
    │   └── bocha_ai_search_provider.py  # AI Search 适配器
    └── fetch/
        ├── http_fetcher.py
        └── html_extractor.py
```

## 日志层级

所有日志都带有清晰的前缀标识：

- `[Server]` - MCP Server 层
- `[Router]` - 路由层
- `[WebService]` - 业务服务层
- `[BochaAI]` - 博查 AI 适配器层
- `research.sources.mcp` - MCP Client 层

## 数据流追踪

### 1. 请求流
```
Research Step
  ↓ (调用 research_client)
MCP Client (mcp_client.py)
  ↓ (构建 MCP 请求)
WebService (web_service.py)
  ↓ (调用搜索提供商)
BochaAISearchProvider (bocha_ai_search_provider.py)
  ↓ (HTTP POST)
博查 AI Search API
```

### 2. 响应流
```
博查 AI Search API
  ↓ (JSON 响应)
BochaAISearchProvider (解析网页+模态卡)
  ↓ (SearchResult 列表)
WebService (转换为领域模型)
  ↓ (标准化结果)
MCP Client (格式化为文本)
  ↓ (返回字典)
Research Step (合并到 items)
```

## 切换 Provider

如果需要切换回其他 Provider：

### 切换到博查 Web Search
```yaml
research:
  provider: "bocha"
```

### 切换到 Metaso
```yaml
research:
  provider: "metaso"
```

### 切换到 Anspire
```yaml
research:
  provider: "anspire"
```

## 故障排查

### 问题 1：API Key 未配置
```
错误: 博查 API Key 未配置
解决: export BOCHA_API_KEY="your-key-here"
```

### 问题 2：MCP 搜索失败
```
错误: MCP研究失败
解决: 检查日志中的详细错误信息，通常是 API 余额不足或网络问题
```

### 问题 3：research 结果未合并
```
错误: 已将 0/1 个 items 的 research 结果合并
解决: 已修复 EvidencePack.item_id 属性，重新运行即可
```

## 性能优化

### 1. 调整超时时间
```yaml
mcp:
  timeout_seconds: 120  # 增加到 120 秒
```

### 2. 调整结果数量
```yaml
mcp:
  max_results: 20  # 增加到 20 条
```

### 3. 启用缓存
请求和响应会自动保存到 `out/runs/.../2_research/` 目录。

## 测试验证

### 1. 检查日志
确认看到以下日志：
- `research.sources.mcp - INFO - 开始 MCP 搜索`
- `[BochaAI] 开始搜索`
- `[BochaAI] ✓ 搜索完成`

### 2. 检查保存的文件
```bash
ls out/runs/*/2_research/
# 应该看到：
# mcp_request_xxx.json
# mcp_response_xxx.json
```

### 3. 检查合并结果
日志应该显示：
```
已将 1/1 个 items 的 research 结果合并
```

## 下一步

1. ✅ 运行完整流程测试
2. ✅ 验证 research 结果正确合并
3. ✅ 检查生成的脚本质量
4. 📊 根据需要调整参数优化

---

**版本**: 1.0.0  
**更新时间**: 2026-01-07  
**作者**: Auto-Podcast Team
