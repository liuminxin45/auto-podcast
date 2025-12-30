# Source Labeling Workflow

## 概述

本文档描述了 Auto-Podcast 系统中的**来源标签自动化工作流**，确保所有 RSS 源和数据源在整个处理流程中始终携带来源标签信息。

## 设计原则

1. **自动化**：无需手动干预，所有来源信息自动传递
2. **一致性**：所有 fetcher 使用统一的字段命名规范
3. **可追溯**：从数据获取到最终输出，来源信息完整保留
4. **可扩展**：添加新 RSS 源时自动适配来源标签机制

## 架构流程

### 1. 数据获取阶段（Fetch Step）

#### Fetcher 输出规范

所有 fetcher 必须在返回的 item 中包含 `source` 字段：

```python
{
    "id": "unique_id",
    "title": "新闻标题",
    "content": "新闻内容",
    "url": "https://...",
    "published_at": "2025-12-30",
    "source": "来源名称",  # 必需字段
    "summary": "摘要",
}
```

#### 已实现的 Fetchers

| Fetcher | 类型 | Source 字段来源 |
|---------|------|----------------|
| `standard_rss` | 标准RSS | `config.name` |
| `sixtys_digest` | 汇总型RSS | `config.name` |
| `ai_daily_news` | API接口 | `config.name` |

**示例配置**：

```yaml
sources:
  rss:
    - name: "AI日报快讯"  # 此名称将作为 source 字段
      fetcher: "ai_daily_news"
      enabled: true
      urls:
        - "https://60s.viki.moe"
```

### 2. 标准化阶段（Normalization）

#### 字段映射

`normalize.py` 将原始 item 转换为标准化格式，保留并增强来源信息：

```python
# 输入: raw item with "source" field
{
    "source": "AI日报快讯",
    ...
}

# 输出: normalized item with multiple source fields
{
    "source": "AI日报快讯",           # 主要来源字段
    "source_name": "AI日报快讯",      # 别名
    "source_info": {                  # 详细来源信息
        "name": "AI日报快讯",
        "domain": "60s.viki.moe",
        "url": "https://...",
        "fetch_time": "2025-12-30T..."
    },
    "source_domain": "60s.viki.moe",
    "source_url": "https://...",
    ...
}
```

#### 关键代码位置

- **文件**: `src/fetch/operations/normalize.py`
- **函数**: `normalize_item()`
- **行**: 104-146

### 3. 去重与处理阶段

来源信息在以下操作中保持不变：

- **去重** (`src/store/operations/dedup.py`)
- **合规验证** (`src/fetch/operations/compliance.py`)
- **日期过滤** (`src/app/pipelines/steps/fetch_step.py`)
- **汇总拆分** (`src/fetch/processors/digest_splitter.py`)

### 4. 选题阶段（Selection Step）

来源信息用于：

- **多样性评分**：计算来源多样性
- **代理信号**：评估来源可信度

**关键代码**：
- `src/topic_selection/processing/proxy_signals.py:101-112`

### 5. 脚本生成阶段（Script Step）

#### 数据模型

`ScriptInputItem` 包含来源字段：

```python
class ScriptInputItem(BaseModel):
    id: str
    title: str
    content: str
    url: str
    published_at: Optional[str] = None
    source: str = ""          # 来源名称
    source_name: str = ""     # 别名
```

#### 来源提取逻辑

`script_step.py` 自动提取来源信息：

```python
# 支持多种格式
source = item.get("source", "")
if isinstance(source, dict):
    source_name = source.get("name", "")
elif isinstance(source, str):
    source_name = source
else:
    source_name = ""

# 降级策略
if not source_name:
    source_name = item.get("source_name", "") or item.get("source_domain", "")
```

**关键代码位置**：
- **文件**: `src/app/pipelines/steps/script_step.py`
- **行**: 37-63

### 6. LLM 提示词（Prompts）

#### 来源标签注入

所有提示词模板自动在新闻列表中添加来源标签：

```python
# 研究型脚本
for i, it in enumerate(items):
    source_label = f"[来源: {it.source}]" if it.source else ""
    item_lines.append(f"{i}. {source_label} {it.title}\n{it.url}")
```

**输出示例**：

```
新闻素材：
1. [来源: AI日报快讯] Meta 数十亿美元收购 Manus
   https://...
2. [来源: 60s-每天60秒读懂世界] 国内新闻汇总
   https://...
```

#### 来源归属要求

提示词明确要求 LLM 在生成内容时标注来源：

```
强约束：
- shownotes 用 Markdown，列出每条新闻的要点与链接，**必须注明来源**
- **重要**：在播客内容中提及新闻时，必须说明来源（如"根据XX报道"、"来自XX消息"）
```

**关键代码位置**：
- **文件**: `src/llm/templates/prompts.py`
- **函数**: 
  - `build_research_script_prompt()` (行 87-88)
  - `build_news_script_prompt()` (行 172-173)
  - `build_detailed_news_script_prompt()` (行 226-227)

### 7. 最终输出

生成的播客脚本包含来源归属：

- **SSML**: "根据AI日报快讯报道，Meta宣布..."
- **Shownotes**: 
  ```markdown
  ## 今日要闻
  
  ### Meta 收购 Manus
  **来源**: AI日报快讯
  - 收购金额达数十亿美元
  - [详细报道](https://...)
  ```

## 添加新 RSS 源的步骤

### 1. 创建 Fetcher（如需要）

如果是标准 RSS，使用 `standard_rss` fetcher。如果是特殊格式，创建新 fetcher：

```python
@register_fetcher("your_fetcher_name")
class YourFetcher(BaseFetcher):
    def fetch_items(self, config, episode_date, timeout_seconds):
        source_name = config.get("name", "默认名称")
        
        # ... 获取数据 ...
        
        return {
            "id": item_id,
            "title": title,
            "content": content,
            "url": url,
            "published_at": date,
            "source": source_name,  # 必须包含
        }
```

### 2. 注册 Fetcher

在 `src/fetch/__init__.py` 中导入：

```python
from .fetchers import your_fetcher  # noqa: F401
```

在 `src/fetch/fetchers/__init__.py` 中导入：

```python
from . import your_fetcher  # noqa: F401
```

### 3. 配置数据源

在 `config/base/settings.yaml` 中添加：

```yaml
sources:
  rss:
    - name: "你的数据源名称"  # 这个名称会自动成为 source 标签
      fetcher: "your_fetcher_name"
      enabled: true
      category: "tech"  # 可选
      urls:
        - "https://your-rss-url.com"
```

### 4. 验证

运行测试确认来源标签正确传递：

```bash
python test_ai_daily_news.py
```

检查输出中的 `source` 字段是否正确。

## 验证清单

添加新 RSS 源后，验证以下各阶段的来源信息：

- [ ] **Fetch 阶段**: 检查 `01_raw_items.jsonl` 中的 `source` 字段
- [ ] **Normalize 阶段**: 检查 `08_final_processed_items.jsonl` 中的 `source_name` 字段
- [ ] **Selection 阶段**: 检查选中的 items 包含来源信息
- [ ] **Script 阶段**: 检查 LLM 输入包含 `[来源: XX]` 标签
- [ ] **Output 阶段**: 检查 shownotes 中标注了来源

## 故障排查

### 问题：来源信息丢失

**可能原因**：
1. Fetcher 未设置 `source` 字段
2. 配置文件中 `name` 字段缺失
3. 中间处理步骤覆盖了字段

**解决方法**：
1. 检查 fetcher 代码确保返回 `source` 字段
2. 检查配置文件确保 `name` 字段存在
3. 在各阶段的 artifacts 中追踪字段变化

### 问题：LLM 输出未包含来源

**可能原因**：
1. 提示词未正确传递来源信息
2. LLM 忽略了来源要求

**解决方法**：
1. 检查 `script_step.py` 中的 `input_items` 是否包含 `source`
2. 检查提示词中是否有 `[来源: XX]` 标签
3. 在提示词中加强来源归属要求

## 技术细节

### 字段优先级

系统按以下优先级提取来源信息：

1. `item["source"]` (如果是字典，取 `["name"]`)
2. `item["source_name"]`
3. `item["source_domain"]`
4. 配置文件中的 `config["name"]`

### 兼容性

系统支持多种来源字段格式：

```python
# 格式1: 字符串
{"source": "AI日报快讯"}

# 格式2: 字典
{"source": {"name": "AI日报快讯", "domain": "60s.viki.moe"}}

# 格式3: 分离字段
{"source_name": "AI日报快讯", "source_domain": "60s.viki.moe"}
```

## 相关文件

### 核心文件

- `src/fetch/core/base.py` - Fetcher 基类定义
- `src/fetch/operations/normalize.py` - 标准化处理
- `src/app/pipelines/steps/script_step.py` - 脚本生成
- `src/llm/templates/prompts.py` - LLM 提示词
- `src/llm/client/api_client.py` - 数据模型定义

### 配置文件

- `config/base/settings.yaml` - RSS 源配置

### 测试文件

- `test_ai_daily_news.py` - 来源标签测试示例

## 最佳实践

1. **命名规范**: 使用清晰、易识别的来源名称
2. **一致性**: 同一来源在不同配置中使用相同名称
3. **可读性**: 来源名称应该适合在播客中口语化表达
4. **简洁性**: 避免过长的来源名称

## 更新日志

- **2025-12-30**: 初始版本，实现完整的来源标签自动化工作流
- **2025-12-30**: 添加 AI 日报快讯 RSS 源作为示例
- **2025-12-30**: 更新 LLM 提示词以强制要求来源归属
