# LangGraph Studio 快速启动

## 3 步开始使用

### 1️⃣ 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
```

### 2️⃣ 打开 LangGraph Studio
- 下载：https://studio.langchain.com/
- 打开项目：选择 `auto-podcast` 目录
- Studio 自动识别 `langgraph.json`

### 3️⃣ 运行流程
- 点击 "Run" 开始执行
- 或点击 "Step" 单步调试
- 实时查看 State 和日志

## 流程图预览

```
fetch → preprocess → research → topic_selection → script 
  → stages → tts → audio_postprocess → assets → store → publish
```

## 常用操作

| 操作 | 说明 |
|------|------|
| **Run** | 完整运行流程 |
| **Step** | 单步执行节点 |
| **Pause** | 暂停执行 |
| **Reset** | 重置状态 |
| **Config** | 修改节点配置 |
| **State** | 查看当前状态 |

## 快速配置示例

**最小化测试配置**：
```json
{
  "fetch": {
    "sources": [{"type": "rss", "url": "https://hnrss.org/frontpage"}],
    "max_items_per_source": 3
  },
  "script": {
    "llm_model": "gpt-4o-mini",
    "target_duration_minutes": 5
  }
}
```

## 产物位置

- 音频：`out/episodes/{episode_id}.mp3`
- 封面：`out/assets/{episode_id}_cover.png`
- RSS：`out/rss/feed.xml`

## 需要帮助？

查看完整文档：`LANGGRAPH_STUDIO_GUIDE.md`

---

**开始可视化开发！** 🎨
