# Auto-Podcast

基于 **LangGraph** 的播客自动生成系统 v2.0

## 架构特点

- **LangGraph 驱动**：所有流程通过 LangGraph 编排，节点完全解耦
- **节点独立配置**：每个节点内部定义 Config Schema，支持运行时覆盖
- **机密管理**：不依赖项目级 `.env`，从系统环境变量读取 API Key
- **小而美**：移除前端/n8n/mcp/测试代码，只保留核心流程

## 主流程

```
fetch → preprocess → research → topic_selection → script → stages → tts → audio_postprocess → assets → store → publish
```

## 使用方式

### 方式一：LangGraph Studio（推荐）

**可视化开发和调试**

1. 安装 LangGraph Studio（需要 LangSmith 账号）
   ```bash
   # 访问 https://studio.langchain.com/ 下载
   ```

2. 配置环境变量
   ```bash
   # 复制环境变量模板
   cp .env.example .env
   
   # 编辑 .env 文件，填入你的 API Key
   OPENAI_API_KEY=your-openai-api-key-here
   ```

3. 在 LangGraph Studio 中打开项目
   - 打开 LangGraph Studio
   - 选择 "Open Project"
   - 选择本项目目录
   - Studio 会自动识别 `langgraph.json` 配置

4. 可视化运行
   - 在 Studio 中查看完整的节点流程图
   - 单步调试每个节点
   - 实时查看 State 变化
   - 修改节点配置并重新运行

### 方式二：命令行运行

**快速批量生成**

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key-here"

# Linux/macOS
export OPENAI_API_KEY="your-api-key-here"
```

### 3. 运行

```bash
# 使用默认配置
python main.py

# 使用自定义配置
python main.py config.yaml
```

## 配置示例

创建 `config.yaml`：

```yaml
fetch:
  sources:
    - type: rss
      url: "https://hnrss.org/frontpage"
  max_items_per_source: 10

script:
  target_duration_minutes: 15
  llm_model: "gpt-4o"

tts:
  voice_mapping:
    主持人A: "zh-CN-XiaoxiaoNeural"
    主持人B: "zh-CN-YunxiNeural"

publish:
  podcast_title: "AI 科技播客"
  podcast_description: "AI 自动生成的科技播客节目"
```

## 产物

运行完成后，在 `out/` 目录下生成：

- **音频文件**：`out/episodes/{episode_id}.mp3`
- **封面**：`out/assets/{episode_id}_cover.png`
- **RSS Feed**：`out/rss/feed.xml`
- **元数据**：`out/published/{episode_id}/metadata.json`

## 目录结构

```
auto-podcast/
├── main.py                 # CLI 主入口
├── studio.py               # LangGraph Studio 入口
├── langgraph.json          # LangGraph Studio 配置
├── .env.example            # 环境变量模板
├── config.example.yaml     # 配置示例
├── src/
│   ├── nodes/             # 12个 LangGraph 节点
│   ├── graphs/            # 主图定义
│   └── schemas/           # State Schema
├── out/                   # 输出目录（运行时生成）
└── requirements.txt       # 依赖
```

## 节点说明

| 节点 | 职责 |
|------|------|
| `fetch` | 抓取原始素材（RSS/网页） |
| `preprocess` | 清洗、去重、分段 |
| `research` | 深度研究、扩展信息 |
| `topic_selection` | 选题、聚类、排序 |
| `script` | 生成播客脚本 |
| `stages` | 脚本分段、角色分配 |
| `tts` | 文本转语音 |
| `audio_postprocess` | 音频拼接、响度标准化 |
| `assets` | 生成封面 |
| `store` | 本地存储（预留云存储接口） |
| `publish` | 生成 RSS（预留发布接口） |
| `subtitles` | 字幕生成（占位，默认禁用） |

## 环境要求

- Python 3.8+
- ffmpeg（音频处理）
- OpenAI API Key
- LangGraph Studio（可选，用于可视化开发）

## 相关文档

- **[LangGraph Studio 快速启动](QUICKSTART_STUDIO.md)** - 3步开始使用 Studio
- **[LangGraph Studio 完整指南](LANGGRAPH_STUDIO_GUIDE.md)** - 详细使用教程
- **[重构总结](REFACTORING_SUMMARY.md)** - v2.0 重构详情

## License

MIT
