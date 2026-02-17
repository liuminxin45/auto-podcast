# 产品设计文档：Discover 自动选题 (Auto Topic Selection)

## 1. 核心理念
在 Discover (发现层) 引入 **"Human-Guided Auto-Selection" (人机协同自动选题)** 模式。
用户不再需要手动逐条筛选海量新闻，而是作为“主编”下达选题指令，由 AI 完成初筛和推荐，最后由用户进行“定稿”确认。

此功能将封装在一个独立的 **"自动选题" (Auto Topic Selection)** 模态框（Modal）中，提供完整的**配置-执行-审核**闭环体验。

---

## 2. 用户流程 (User Flow)

### 阶段一：触发与配置 (Trigger & Config)
1. **入口**：在 Discover 面板顶部（搜索栏旁）新增高亮按钮 **[✨ 自动选题]**。
2. **配置弹窗**：点击后弹出模态框，要求用户输入/确认选题标准：
   - **核心主题 (Topic)**: 必填，如 "DeepSeek 发布的最新影响"。
   - **时效性 (Time Range)**: 必填，默认 24h (24h / 3天 / 7天 / 不限)。
   - **AI 选题偏好 (Prompt Context)**: 选填，文本域。给 AI 的额外判断指令，例如 "侧重技术分析，忽略股价波动"。
   - **数量控制**: 期望入选数量 (默认 5-10 条)。

### 阶段二：执行与可视化 (Execution & Visualization)
1. **启动**：点击 [开始选题]。
2. **可视化进度**：模态框进入“执行态”，展示线性进度条或步骤图：
   - ⏳ **采集 (Fetching)**: 调用 Radar 采集数据 (展示：抓取 50 条...)
   - 🔍 **初筛 (Filtering)**:按时效性、基础关键词过滤 (展示：保留 30 条...)
   - 🧠 **AI 研判 (LLM Analysis)**: 并发分析内容与主题的匹配度 (展示：AI 正在阅读...)
   - ✨ **生成候选 (Generating)**: 排序并生成推荐理由。

### 阶段三：人工审核与反馈 (Review & Feedback)
1. **结果呈现**：执行完成后，模态框展示左右/上下两栏布局：
   - **✅ 拟入选 (Selected)**: AI 认为高度匹配的内容 (带推荐理由 + 匹配分)。
   - **❌ 拟淘汰 (Rejected)**: AI 认为不匹配或低质量的内容 (带淘汰理由)。
2. **人工干预**：
   - 用户可以把“拟淘汰”里的捞回来，或把“拟入选”的踢出去。
   - **关键交互**：这是最直接的 RLHF (Reinforcement Learning from Human Feedback) 雏形。用户的拖拽/勾选行为即是对 AI 的纠正。
3. **完成**：点击 [确认并整理]，将最终“拟入选”列表批量加入 **整理列表 (Organize List)**，并自动关闭 Discover 面板，跳转至 Organize 面板。

---

## 3. 功能详细设计

### 3.1 交互界面 (UI/UX)

**入口位置**: `DiscoverPanel` Header 区域。

**模态框 (Modal) - "自动选题助手"**:
- **宽度**: 800px (宽屏以容纳审核列表)。
- **Step 1: 设定标准**
  - Input: `主题关键词` (复用当前 Discover 搜索词或独立)
  - RadioGroup: `时效性` (24h, 3d, 1w)
  - TextArea: `补充指令` (Placeholder: "例如：优先保留有代码示例的文章...")
- **Step 2: 智能处理中**
  - Progress Bar: 实时进度的百分比。
  - Log Console (折叠/精简): 滚动显示 "正在分析文章 A...", "文章 B 时效性不符跳过..."。
- **Step 3: 选题定稿**
  - **精选区 (High Confidence)**: 卡片列表，展示 标题 + 来源 + **AI 推荐语 (One-liner)**。
  - **备选区/回收站 (Low Confidence)**: 折叠或灰色显示，点击可展开查看。
  - **Action**: [确认选题 (X条)] -> 进入整理。

### 3.2 必要的配置项 (Configuration)

为支持此功能，需扩展配置结构 (建议复用 `topic_selection/config.py`):

```python
@dataclass
class AutoSelectionConfig:
    target_topic: str          # 用户输入的主题
    time_range_hours: int = 24 # 时效性限制
    focus_instruction: str = "" # 用户补充的额外指令 (Prompt Context)
    min_match_score: int = 70   # AI 打分阈值 (0-100)
    max_items: int = 10         # 期望最大数量
```

### 3.3 AI 核心逻辑 (LLM Strategy)

在 `topic_selection` 节点中新增模式 `analyze_relevance`。

**Prompt 设计思路**:
```text
你是一个专业的主编。
当前选题任务：{target_topic}
额外要求：{focus_instruction}

请分析以下文章：
标题：{title}
摘要：{summary}

请输出 JSON:
{
  "score": 0-100, // 匹配度打分
  "decision": "keep" | "drop",
  "reason": "简短的一句话理由，说明为何入选或淘汰",
  "angle": "建议切入角度"
}
```

---

## 4. 技术实现路径 (Technical Implementation)

### 4.1 后端 (Python Protocol)
1. **修改 `nodes/topic_selection/node.py`**:
   - 之前是 `clustering` (聚类)，现在新增 `ranking` (打分筛选) 逻辑。
   - 接收 `AutoSelectionConfig`。
   - 遍历 `researched_contents`，并发调用 LLM 进行评分。
   - 返回带有 `_topic_score`, `_topic_reason` 的内容列表。

2. **修改 `nodes/topic_selection/config.py`**:
   - 增加上述配置字段。

### 4.2 前端 (React/Electron)
1. **新建组件 `AutoTopicModal.tsx`**:
   - 管理 3 个步骤的状态 (Config -> Running -> Review)。
   - 调用 `window.electronAPI.runNode('topic_selection', ...)` 或复用 `runRadar` + `runTopicSelection` 组合。
   - **特别注意**：前端需要先调用 `Fetch` (采集)，拿到数据后，再把数据传给 `TopicSelection` (筛选)。或者在后端编排成一个 `Pipeline`。
   - *建议方案*：为了可视化，前端控制流程：
     - Step 1: Call `radarRunOnce` (采集) -> Update Progress.
     - Step 2: Call `runLLMAnalysis` (前端直接调 LLM 或调后端 Node) -> Update Progress.
     - Step 3: Render Results.

### 4.3 数据流向
`DiscoverPanel` -> `AutoTopicModal` -> (User Config) -> `Electron/Python Fetch` -> `Python LLM Select` -> (User Review) -> `Organize List`.

---

## 5. 验收标准 (Acceptance Criteria)
1. **可用性**: 用户输入主题后，点击一次即可看到带理由的推荐列表。
2. **准确性**: 能够过滤掉非指定时效的新闻；能够根据“额外指令”剔除不相关内容。
3. **可控性**: 用户最后必须能“一键剔除”AI 选错的，保证进入整理列表的数据是干净的。
4. **性能**: 50 条新闻的筛选处理时间控制在 30 秒内 (取决于 LLM 并发)。

---

## 6. 后续优化 (Future Iteration)
- **记忆优化**: 保存用户的 `focus_instruction` 作为默认偏好。
- **Few-Shot Learning**: 将用户“剔除”的操作记录下来，下次 Prompt 里带上“不要类似 X 的文章”。
