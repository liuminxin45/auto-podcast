# PodFlow Studio

PodFlow Studio 是一个本地优先的单人新闻播客生产流水线，默认服务“通勤早咖啡”这类 5-8 分钟单人新闻早报：采集素材，生成事实卡片和可编辑稿件，合成或替换语音，自动成片，并输出 RSS / 发布包。

## What it does

PodFlow Studio 解决的是个人创作者每天做一期新闻简报的重复生产问题。

默认输入：

- 离线 demo 新闻条目、RSS / 网页素材或手动笔记；
- 可选人工编辑意见；
- 可选真实 LLM / TTS provider 配置。

默认输出：

- `facts.json` 结构化事实卡片；
- `script.generated.json` 机器生成稿；
- `script.edited.json` 可人工编辑稿；
- `final.mp3`，如果本机缺少 ffmpeg 则降级为 `final.wav`；
- `feed.xml`；
- `dist/episodes/<episode_id>/` 发布包。

## Default workflow

```text
数据源采集
  -> 新闻筛选 / 去重 / 归并
  -> 事实卡片
  -> 单人新闻早报稿
  -> 人工手调稿件
  -> AI TTS / 人声录制替换
  -> 自动音频成片
  -> RSS / 发布包输出
```

默认 preset 是 `morning_news_brief`：

- `content_type: news_brief`
- `num_hosts: 1`
- `target_duration_minutes: 5-8`
- `news_item_count: 3-5`
- `tone: clear, concise, commute-friendly`
- `language: zh-CN`

## Quick start

```bash
npm install
npm run setup:python
npm run demo:news
```

demo 不依赖外网、LLM key 或 TTS key。没有真实 TTS 时会生成 mock WAV 语音片段；如果本机 ffmpeg 可用，会导出 `final.mp3`，否则导出 `final.wav` 并在报告中标记降级。

启动桌面开发环境：

```bash
npm run dev
```

## Demo episode

离线 demo 位于：

```text
examples/demo-news/
  input/
    sample-items.json
    manual-notes.md
  expected/
    README.md
  output/
    # npm run demo:news 后生成，默认不提交
```

运行后重点检查：

```text
examples/demo-news/output/facts.json
examples/demo-news/output/script.generated.json
examples/demo-news/output/script.edited.json
examples/demo-news/output/final.mp3 或 final.wav
examples/demo-news/output/feed.xml
examples/demo-news/output/run_report.json
examples/demo-news/output/dist/episodes/demo_morning_news_001/
```

`publish.public_base_url` 为空时，RSS 只用于本地预览，不是公网可订阅 feed；`run_report.json` 会明确记录该 warning。

## Core concepts

`EpisodeRun` 表示一次完整播客生产运行，包含 preset、source inputs、facts、selected topics、script、edited script、voice segments、audio outputs、publish outputs 和 run report。

`FactCard` 是素材和稿件之间的事实层。稿件生成阶段基于 facts，而不是直接把原始素材拼进 prompt。

`ScriptSegment` 是结构化稿件段落。TTS 优先消费 `edited_script`，没有编辑稿时才使用 generated script。每段都可以独立重配音或用真人录音替换。

`AudioAssembly` 负责工程化成片：合并语音片段、加入段间停顿、可用时做响度标准化，输出最终音频和 `audio_report.json`。

`PublishPackage` 输出 `final.*`、`feed.xml`、`episode.json` 和 `run_report.json`。RSS enclosure 支持 `public_base_url`，没有公开 URL 时只生成本地预览 RSS。

## Current status

已可用：

- 默认 `morning_news_brief` preset；
- 离线 demo 新闻输入；
- FactCard 生成；
- deterministic/mock script generator；
- `edited_script` 优先进入 TTS；
- mock TTS 音频片段；
- AudioAssembly 成片与降级报告；
- RSS / 发布包输出；
- 无外部 API key 的端到端测试。

仍为 secondary / experimental：

- 多主持播客；
- 长节目故事稿；
- 桌面 UI 中的复杂构思与写作辅助；
- 真实 TTS provider 的生产级稳定性；
- 云端发布和公网托管。

## Roadmap

- 给 `EpisodeRun` 补 JSON Schema 和迁移说明；
- 增强 RSS 校验和公开托管指南；
- 在桌面 UI 中把 FactCard 和 edited script 作为主入口；
- 增加真实 TTS provider 的能力矩阵和故障降级策略；
- 支持单段真人录音替换的更完整报告。

## Non-goals

- 不是通用剪辑软件；
- 不是新闻 CMS；
- 不是多人播客平台；
- 不以海量数据源聚合为第一目标；
- 当前优先保证单人新闻早报闭环。
