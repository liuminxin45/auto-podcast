# LangGraph Studio 使用指南

本指南介绍如何使用 LangGraph Studio 可视化开发和调试 Auto-Podcast 项目。

## 什么是 LangGraph Studio？

LangGraph Studio 是 LangChain 官方提供的可视化开发工具，用于：
- **可视化流程图**：查看完整的节点流程和连接关系
- **单步调试**：逐节点执行，查看每一步的输入输出
- **状态检查**：实时查看 State 的变化
- **配置调整**：动态修改节点配置并重新运行
- **性能分析**：查看每个节点的执行时间

## 安装 LangGraph Studio

### 1. 前置要求
- LangSmith 账号（免费注册：https://smith.langchain.com/）
- Python 3.8+
- 项目依赖已安装

### 2. 下载 Studio
访问 https://studio.langchain.com/ 下载适合你操作系统的版本：
- macOS
- Windows
- Linux

## 配置项目

### 1. 环境变量设置

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必需的 API Keys：
```env
# 必需
OPENAI_API_KEY=<api-key>

# 可选（如果使用其他 LLM）
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key
```

### 2. 项目配置文件

项目已包含 `langgraph.json` 配置文件：
```json
{
  "dependencies": ["."],
  "graphs": {
    "podcast_agent": "./src/graphs/podcast_graph.py:create_podcast_graph"
  },
  "env": ".env"
}
```

**配置说明**：
- `dependencies`: 项目依赖路径
- `graphs`: 定义可用的图及其入口函数
- `env`: 环境变量文件路径

## 使用 LangGraph Studio

### 1. 打开项目

1. 启动 LangGraph Studio
2. 点击 "Open Project"
3. 选择 `auto-podcast` 项目目录
4. Studio 会自动识别 `langgraph.json` 并加载图

### 2. 查看流程图

打开项目后，你会看到完整的播客生成流程图：

```
┌─────────┐
│  fetch  │
└────┬────┘
     │
┌────▼────────┐
│ preprocess  │
└────┬────────┘
     │
┌────▼────────┐
│  research   │
└────┬────────┘
     │
┌────▼────────────────┐
│ topic_selection     │
└────┬────────────────┘
     │
┌────▼────────┐
│   script    │
└────┬────────┘
     │
┌────▼────────┐
│   stages    │
└────┬────────┘
     │
┌────▼────────┐
│    tts      │
└────┬────────┘
     │
┌────▼───────────────────┐
│ audio_postprocess      │
└────┬───────────────────┘
     │
┌────▼────────┐
│   assets    │
└────┬────────┘
     │
┌────▼────────┐
│   store     │
└────┬────────┘
     │
┌────▼────────┐
│  publish    │
└─────────────┘
```

### 3. 配置节点参数

在 Studio 中，你可以为每个节点配置参数：

**示例：配置 fetch 节点**
```json
{
  "fetch": {
    "sources": [
      {
        "type": "rss",
        "url": "https://hnrss.org/frontpage"
      }
    ],
    "max_items_per_source": 5
  }
}
```

**示例：配置 script 节点**
```json
{
  "script": {
    "llm_model": "gpt-4o-mini",
    "target_duration_minutes": 10,
    "num_hosts": 2
  }
}
```

### 4. 运行和调试

#### 完整运行
1. 点击 "Run" 按钮
2. 输入初始 State（可选，使用默认值）
3. 观察流程执行

#### 单步调试
1. 点击 "Step" 按钮
2. 每次执行一个节点
3. 查看当前节点的输入输出
4. 检查 State 的变化

#### 断点调试
1. 在任意节点上设置断点
2. 运行流程，执行会在断点处暂停
3. 检查当前状态
4. 继续或单步执行

### 5. 查看 State

在 Studio 右侧面板，你可以实时查看 `PodcastState` 的所有字段：

```python
{
  "episode_id": "20260203_213000",
  "created_at": "2026-02-03T21:30:00",
  "raw_contents": [...],
  "cleaned_contents": [...],
  "selected_topic": {...},
  "script": {...},
  "stages": [...],
  "audio_segments": [...],
  "final_audio_path": "out/episodes/20260203_213000.mp3",
  "cover_path": "out/assets/20260203_213000_cover.png",
  "rss_path": "out/rss/feed.xml",
  "logs": [...],
  "errors": []
}
```

### 6. 性能分析

Studio 提供性能分析功能：
- 每个节点的执行时间
- 总执行时间
- 瓶颈识别
- 资源使用情况

## 常见使用场景

### 场景 1：快速测试新配置

1. 在 Studio 中修改节点配置
2. 点击 "Run" 立即测试
3. 查看结果，无需重启程序

### 场景 2：调试节点错误

1. 运行流程直到出错
2. 查看错误节点的输入
3. 检查 State 中的数据
4. 修复代码后重新加载

### 场景 3：优化流程性能

1. 运行完整流程
2. 查看性能分析报告
3. 识别慢节点
4. 优化代码或配置

### 场景 4：开发新节点

1. 创建新节点代码
2. 在 Studio 中添加到图中
3. 单步测试新节点
4. 验证输入输出正确

## 与命令行的对比

| 特性 | LangGraph Studio | 命令行 (main.py) |
|------|------------------|------------------|
| 可视化 | ✅ 完整流程图 | ❌ 无 |
| 调试 | ✅ 单步调试 | ❌ 只能看日志 |
| 配置修改 | ✅ 实时修改 | ❌ 需要编辑文件 |
| 状态检查 | ✅ 实时查看 | ❌ 只能看日志 |
| 性能分析 | ✅ 详细报告 | ❌ 无 |
| 批量运行 | ❌ 不适合 | ✅ 适合 |
| 自动化 | ❌ 不适合 | ✅ 适合 |

**建议**：
- **开发调试**：使用 LangGraph Studio
- **生产运行**：使用命令行 `main.py`

## 故障排查

### 问题 1：Studio 无法识别项目

**解决方案**：
- 确保 `langgraph.json` 在项目根目录
- 检查 JSON 格式是否正确
- 确保 Python 环境已激活

### 问题 2：节点执行失败

**解决方案**：
- 检查 `.env` 文件中的 API Keys
- 查看 Studio 的错误日志
- 确认依赖已正确安装

### 问题 3：State 显示不完整

**解决方案**：
- 刷新 Studio 界面
- 重新运行流程
- 检查节点是否正确更新 State

## 最佳实践

1. **开发新功能**：先在 Studio 中测试，确认无误后再批量运行
2. **调试错误**：使用单步调试，逐节点排查问题
3. **性能优化**：定期查看性能报告，优化慢节点
4. **配置管理**：在 Studio 中测试配置，确认后保存到 `config.yaml`
5. **版本控制**：将测试通过的配置提交到 Git

## 更多资源

- LangGraph 文档：https://langchain-ai.github.io/langgraph/
- LangGraph Studio 文档：https://docs.smith.langchain.com/
- LangSmith 平台：https://smith.langchain.com/

---

**开始使用 LangGraph Studio，享受可视化开发体验！** 🚀
