# 快速开始 - 分段播客系统

## ✅ 已完成的修改

1. **修改了 `src/app/pipelines/episode_pipeline.py`**
   - 替换为 `ScriptStepSegmented` 和 `AudioStepSegmented`
   - 系统现在会生成 6 个独立的脚本段落和音频文件

2. **BGM 已设为可选**
   - 如果没有 BGM 文件，系统会自动跳过，仅合并音频段落
   - 不会因为缺少 BGM 而报错

## 🚀 立即运行

```bash
python run.py
```

## 📂 预期输出

运行后，你会在 `out/runs/{date}/{run_id}/` 看到：

```
2_script/
├── segments/
│   ├── S0.json  # 开场白
│   ├── S1.json  # 新闻概览
│   ├── S2.json  # 历史上的今天
│   ├── S3.json  # 新闻详情
│   ├── S4.json  # 深入分析
│   └── S5.json  # 结束语
├── 2025-12-30.segments.json      # 所有段落汇总
└── 2025-12-30.full_script.txt    # 完整脚本文本

3_tts/
├── segments/
│   ├── S0.mp3   # 开场白音频
│   ├── S1.mp3   # 新闻概览音频
│   ├── S2.mp3   # 历史音频
│   ├── S3.mp3   # 新闻详情音频
│   ├── S4.mp3   # 深入分析音频
│   └── S5.mp3   # 结束语音频
└── manifest.json  # 完整的元数据

4_render/
└── 2025-12-30.final.mp3  # 最终合并的完整播客
```

## 🎯 6 个段落说明

- **S0 (OPENING)**: 15-20秒 - "大家好，我是民心，今天是2025年12月30日..."
- **S1 (OVERVIEW)**: 30-45秒 - 快速浏览今天的3-6条新闻
- **S2 (HISTORY)**: 20-30秒 - 历史上的今天发生了什么
- **S3 (DETAIL_NEWS)**: 60-120秒 - 逐条详细讲解新闻
- **S4 (DEEP_DIVE)**: 60-90秒 - 深入分析一个主题
- **S5 (CLOSING)**: 15-20秒 - 总结和告别

## 🔍 验证结果

### 1. 查看生成的段落数量
```bash
# 应该看到 6 个 JSON 文件
ls out/runs/20251230/*/2_script/segments/

# 应该看到 6 个 MP3 文件
ls out/runs/20251230/*/3_tts/segments/
```

### 2. 查看 manifest
```bash
# 查看完整的元数据
cat out/runs/20251230/*/3_tts/manifest.json
```

### 3. 播放音频
```bash
# 播放单个段落
ffplay out/runs/20251230/*/3_tts/segments/S0.mp3

# 播放最终合并的播客
ffplay out/runs/20251230/*/4_render/*.final.mp3
```

## 🎵 添加 BGM（可选）

如果你想添加背景音乐：

1. 准备两个音频文件：
   - `transition.mp3` (0.5-1.2秒) - 段落间过渡音效
   - `outro.mp3` (2-3秒) - 结尾音乐

2. 放到这里：
   ```bash
   assets/bgm/transition.mp3
   assets/bgm/outro.mp3
   ```

3. 重新运行：
   ```bash
   python run.py
   ```

系统会自动在段落间插入 BGM。

## ⚡ 缓存机制

第二次运行时，已经生成的段落会被重用：

```
✓ S0 使用缓存
✓ S1 使用缓存
✓ S2 使用缓存
...
```

如果想重新生成某个段落：

```bash
# 删除该段落的文件
rm out/runs/20251230/*/2_script/segments/S3.json
rm out/runs/20251230/*/3_tts/segments/S3.mp3

# 重新运行
python run.py
```

## 📝 查看日志

日志会显示每个段落的生成过程：

```
生成段落 S0 (OPENING)
✓ S0 生成成功: 18秒
生成 S0 TTS...
✓ S0 TTS完成: 18.5秒, 耗时 2500ms
```

## 🔧 如果遇到问题

### 问题：仍然只生成一个 mp3
**检查**: 确认 `src/app/pipelines/episode_pipeline.py` 已经修改

### 问题：ffmpeg 错误
**解决**: 
```bash
# 检查 ffmpeg
ffmpeg -version

# 如果没有，安装：
# Windows: 下载 https://ffmpeg.org/
# macOS: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg
```

### 问题：LLM 调用失败
**检查**: 环境变量是否正确设置
```bash
echo $MOONSHOT_API_KEY
echo $DEEPSEEK_API_KEY
```

## 🎉 成功标志

如果一切正常，你会看到：

✅ 6 个脚本 JSON 文件
✅ 6 个音频 MP3 文件
✅ 1 个 manifest.json
✅ 1 个最终的 final.mp3
✅ 日志显示每个段落的生成过程

---

**现在就运行 `python run.py` 试试吧！**
