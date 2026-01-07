# 脚本生成数据流转问题诊断与解决方案

## 问题描述

用户发现 `enhanced_items.json` 包含了丰富的 research 数据（支持证据、论点、验证结论等），但生成的播客脚本却很干瘪，没有利用这些证据。

---

## 问题根源分析

### 问题 1：Research 证据数据未完整传递

**症状**：
- `enhanced_items.json` 包含详细的 `research_main_evidence`（5条证据，每条包含来源、内容、相关度等）
- 但脚本生成时只使用了简单的 `research_evidence` 摘要："找到 10 条支持证据，平均评分 0.76"

**根本原因**：
在 `script_step_segmented.py` 的 `_prepare_render_params` 方法中，只添加了简单摘要，没有传递详细证据：

```python
# ❌ 之前的代码（只传递摘要）
if news_items[0].research_evidence:
    deep_facts += f"\n\n【深度调研补充】\n{news_items[0].research_evidence}"
    # "找到 10 条支持证据，平均评分 0.76" ← 太简略！
```

### 问题 2：缺少数据流转验证

**症状**：
- 数据在 ResearchStep → ScriptStep 传递过程中丢失或简化
- 没有日志记录数据传递的完整性
- 无法及时发现数据缺失问题

**根本原因**：
- 没有验证 `items_selected` 是否包含完整的 research 数据
- 没有记录传递给 LLM 的数据大小和内容
- 缺少数据流转的可观测性

---

## 数据流转路径

```
┌─────────────────────────────────────────────────────────────┐
│                    ResearchStep                              │
│  1. 调用 ResearchPipeline.run()                              │
│  2. 返回 evidence_packs (包含详细证据)                        │
│  3. 合并到 ctx.items_selected                                │
│  4. 保存到 enhanced_items.json                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              enhanced_items.json (磁盘文件)                   │
│  {                                                           │
│    "id": "be89a7c2ba2c0ebf",                                │
│    "title": "特斯拉遭遇滑铁卢...",                            │
│    "research_evidence": "找到 10 条支持证据...",  ← 简单摘要  │
│    "research_main_evidence": [                   ← 详细证据  │
│      {                                                       │
│        "source_title": "暴跌60%!特斯拉欧洲销量...",          │
│        "content": "分析认为,特斯拉此次遭遇...",               │
│        "relevance_score": 0.75,                             │
│        ...                                                   │
│      },                                                      │
│      ...5条证据                                              │
│    ],                                                        │
│    "research_claims": ["特斯拉遭遇滑铁卢..."],               │
│    "research_verdict": "supported",                         │
│    "research_confidence": 0.76                              │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ScriptStepSegmented                         │
│  1. 读取 ctx.items_selected                                  │
│  2. ❌ 之前：只使用 research_evidence (简单摘要)             │
│  3. ✅ 现在：提取 research_main_evidence (详细证据)          │
│  4. 构建 deep_facts (传递给 LLM)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM (脚本生成)                               │
│  输入: deep_facts (包含详细证据)                              │
│  输出: 播客脚本                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 解决方案

### 1. 修复数据传递逻辑

**修改文件**: `src/app/pipelines/steps/script_step_segmented.py`

**修改内容**: 在 `_prepare_render_params` 方法中，提取并传递详细的 research 证据：

```python
# ✅ 修复后的代码
if news_items:
    first_item = ctx.items_selected[0]
    
    # 1. 添加 research_claims（关键论点）
    research_claims = first_item.get("research_claims", [])
    if research_claims:
        claims_text = "\n".join([f"- {claim}" for claim in research_claims])
        deep_facts += f"\n\n【关键论点】\n{claims_text}"
    
    # 2. 添加详细的支持证据（research_main_evidence）
    main_evidence = first_item.get("research_main_evidence", [])
    if main_evidence:
        deep_facts += f"\n\n【支持证据】（共 {len(main_evidence)} 条）"
        for i, evidence in enumerate(main_evidence[:5], 1):  # 最多使用前5条
            source_title = evidence.get("source_title", "未知来源")
            content = evidence.get("content", "")
            published_at = evidence.get("published_at", "")
            relevance_score = evidence.get("relevance_score", 0)
            
            # 截取内容前300字符
            content_preview = content[:300] if content else ""
            
            deep_facts += f"\n\n证据 {i}：{source_title}"
            if published_at:
                deep_facts += f"\n发布时间：{published_at}"
            deep_facts += f"\n相关度：{relevance_score:.2f}"
            if content_preview:
                deep_facts += f"\n内容：{content_preview}..."
    
    # 3. 添加验证结论
    verdict = first_item.get("research_verdict", "")
    confidence = first_item.get("research_confidence", 0)
    if verdict:
        verdict_map = {
            "supported": "已验证支持",
            "refuted": "已验证反驳",
            "uncertain": "证据不足"
        }
        verdict_text = verdict_map.get(verdict, verdict)
        deep_facts += f"\n\n【验证结论】\n{verdict_text}（置信度：{confidence:.2f}）"
```

**效果**：
- 之前：`deep_facts` 只有 ~100 字符（标题 + 简单摘要）
- 现在：`deep_facts` 有 ~2000+ 字符（标题 + 论点 + 5条详细证据 + 验证结论）

---

### 2. 添加数据验证机制

**修改文件**: `src/app/pipelines/steps/script_step_segmented.py`

**修改内容**: 在 `execute` 方法开始时添加数据验证：

```python
# ========== 数据验证：检查 items_selected 是否包含 research 数据 ==========
research_cfg = cfg.get("research", {})
strict_mode = research_cfg.get("strict_validation", True)

self.logger.info(f"开始验证 {len(ctx.items_selected)} 个 items 的 research 数据")

items_with_research = 0
items_without_research = []

for item in ctx.items_selected:
    item_id = item.get("id", "unknown")
    has_research = (
        item.get("research_evidence") or 
        item.get("research_claims") or 
        item.get("research_main_evidence")
    )
    
    if has_research:
        items_with_research += 1
        # 记录详细信息
        evidence_count = len(item.get("research_main_evidence", []))
        claims_count = len(item.get("research_claims", []))
        self.logger.debug(
            f"Item {item_id}: {evidence_count} 条证据, {claims_count} 个论点"
        )
    else:
        items_without_research.append(item_id)

self.logger.info(
    f"Research 数据检查: {items_with_research}/{len(ctx.items_selected)} 个 items 包含 research 数据"
)

if items_without_research:
    warning_msg = f"警告: {len(items_without_research)} 个 items 缺少 research 数据"
    self.logger.warning(warning_msg)
    
    if strict_mode and items_with_research == 0:
        raise ValidationError(
            f"严格模式: 所有 items 都缺少 research 数据，无法生成高质量脚本"
        )
```

**效果**：
- ✅ 及时发现缺少 research 数据的 items
- ✅ 严格模式下，如果所有 items 都缺少数据，立即中止并报错
- ✅ 非严格模式下，记录警告但继续执行

---

### 3. 添加数据流转日志

**修改文件**: `src/app/pipelines/steps/script_step_segmented.py`

**修改内容**: 在 `_prepare_render_params` 方法结束时添加详细日志：

```python
# ========== 记录传递给 LLM 的数据摘要 ==========
self.logger.info("=" * 60)
self.logger.info("传递给 LLM 的数据摘要:")
self.logger.info(f"  - 新闻条数: {len(news_items)}")
self.logger.info(f"  - Deep dive 主题: {deep_topic}")
self.logger.info(f"  - Deep facts 长度: {len(deep_facts)} 字符")

# 记录 deep_facts 的前500字符（用于调试）
deep_facts_preview = deep_facts[:500] if len(deep_facts) > 500 else deep_facts
self.logger.info(f"  - Deep facts 预览:\n{deep_facts_preview}...")

# 统计 research 数据
total_evidence = sum(
    len(item.get("research_main_evidence", [])) 
    for item in ctx.items_selected
)
total_claims = sum(
    len(item.get("research_claims", [])) 
    for item in ctx.items_selected
)
self.logger.info(f"  - 总证据数: {total_evidence}")
self.logger.info(f"  - 总论点数: {total_claims}")
self.logger.info("=" * 60)
```

**效果**：
- ✅ 清晰显示传递给 LLM 的数据大小
- ✅ 预览 `deep_facts` 的内容，确认包含详细证据
- ✅ 统计总证据数和论点数，便于调试

---

## 日志输出对比

### 修复前（数据缺失）

```
INFO - Script - start - 4 items, 6 segments to generate
INFO - Deep dive 数据准备完成: 1 个论点, 0 条证据, 验证结论: supported
# ❌ 没有详细证据，deep_facts 只有 ~100 字符
```

### 修复后（数据完整）

```
INFO - 开始验证 4 个 items 的 research 数据
INFO - Research 数据检查: 4/4 个 items 包含 research 数据
INFO - Script - start - 4 items, 6 segments to generate
INFO - Deep dive 数据准备完成: 1 个论点, 5 条证据, 验证结论: supported
INFO - ============================================================
INFO - 传递给 LLM 的数据摘要:
INFO -   - 新闻条数: 4
INFO -   - Deep dive 主题: 特斯拉遭遇滑铁卢：2025 欧洲销量大跌 28%...
INFO -   - Deep facts 长度: 2156 字符
INFO -   - Deep facts 预览:
特斯拉遭遇滑铁卢：2025 欧洲销量大跌 28%，主要市场几乎全军覆没

【关键论点】
- 特斯拉遭遇滑铁卢：2025 欧洲销量大跌 28%，主要市场几乎全军覆没

【支持证据】（共 5 条）

证据 1：暴跌60%!特斯拉欧洲销量遭遇滑铁卢特斯拉_新浪财经_新浪网
发布时间：2025-02-06T14:24:00+08:00
相关度：0.75
内容：分析认为,特斯拉此次遭遇滑铁卢可能是因为欧洲电动汽车市场竞争加剧、通胀压力高企、消费者信心下降等,同时,马斯克作为特斯拉CEO,不仅在不受欧洲欢迎的特朗普政府中扮演了重要角色,近期还屡屡在德国政治问题上表态,可能也会影响品牌形象。 特斯拉欧洲销量遭遇滑铁卢,马斯克难逃其咎。 根据德国汽车工业协会(VDA)的最新数据, 特斯拉在德国1月份的新车注册量同比下降60% ,是在德国月销量超过1000辆的汽车制造商中,降幅最大的一家...

证据 2：暴跌60%!特斯拉欧洲销量遭遇滑铁卢
发布时间：2025-02-21T13:54:44+08:00
相关度：0.75
内容：...

【验证结论】
已验证支持（置信度：0.76）
INFO -   - 总证据数: 15
INFO -   - 总论点数: 4
INFO - ============================================================
# ✅ 数据完整，deep_facts 有 2156 字符，包含详细证据
```

---

## 预期效果

### 修复前的脚本（干瘪）

```
=== S3: 深度 (285秒) ===
接着刚才那条消息，我们慢放一下。特斯拉在欧洲，好像遇到坎儿了。

公开数据显示，今年它在欧洲销量下滑明显。同比跌了28%。几个主要市场，几乎都没什么起色。

这情况有点像一家网红餐厅。刚开业时，大家排队去打卡。但现在新店越开越多，口味变化不大，老顾客自然就分流了。特斯拉在欧洲，正面临类似的局面。

为什么现在问题突出了？因为欧洲电动车市场的格局变了...
# ❌ 没有引用具体数据和来源，缺乏说服力
```

### 修复后的脚本（丰富）

```
=== S3: 深度 (285秒) ===
接着刚才那条消息，我们慢放一下。特斯拉在欧洲，好像遇到坎儿了。

根据德国汽车工业协会（VDA）的最新数据，特斯拉在德国1月份的新车注册量同比下降60%，是在德国月销量超过1000辆的汽车制造商中，降幅最大的一家。不仅限于德国，法国和英国的销量也分别同比下降63%和8%。

这情况有点像一家网红餐厅。刚开业时，大家排队去打卡。但现在新店越开越多，口味变化不大，老顾客自然就分流了。特斯拉在欧洲，正面临类似的局面。

为什么现在问题突出了？分析认为，特斯拉此次遭遇滑铁卢可能是因为欧洲电动汽车市场竞争加剧、通胀压力高企、消费者信心下降等。同时，马斯克作为特斯拉CEO，不仅在不受欧洲欢迎的特朗普政府中扮演了重要角色，近期还屡屡在德国政治问题上表态，可能也会影响品牌形象...
# ✅ 引用了具体数据、来源和分析，更有说服力
```

---

## 验证清单

运行 `python run.py --step all` 后，检查以下日志：

### ✅ ResearchStep 日志
```
INFO - 开始验证 4 个 evidence packs (strict=True)
INFO - Evidence Packs - 验证 4 项数据
INFO - 已将 4/4 个 items 的 research 结果合并
INFO - 开始验证 4 个 enhanced items (strict=True)
INFO - Enhanced Items - 验证 4 项数据
INFO - 增强后的 items 已保存: .../enhanced_items.json
```

### ✅ ScriptStep 日志
```
INFO - 开始验证 4 个 items 的 research 数据
INFO - Research 数据检查: 4/4 个 items 包含 research 数据
INFO - Deep dive 数据准备完成: 1 个论点, 5 条证据, 验证结论: supported
INFO - ============================================================
INFO - 传递给 LLM 的数据摘要:
INFO -   - Deep facts 长度: 2156 字符  ← 应该 > 1000 字符
INFO -   - 总证据数: 15                ← 应该 > 0
INFO -   - 总论点数: 4                 ← 应该 > 0
INFO - ============================================================
```

### ✅ 生成的脚本
- 深度段落应该引用具体数据和来源
- 应该包含多个分析角度
- 应该有更丰富的细节和论证

---

## 总结

### 问题根源
1. **数据传递不完整**：只传递了简单摘要，没有传递详细证据
2. **缺少验证机制**：无法及时发现数据缺失
3. **缺少可观测性**：没有日志记录数据流转

### 解决方案
1. **修复数据传递**：提取并传递 `research_main_evidence` 的详细证据
2. **添加验证机制**：在 ScriptStep 开始时验证 research 数据完整性
3. **添加详细日志**：记录传递给 LLM 的数据大小和内容摘要

### 预期效果
- ✅ 脚本更丰富，引用具体数据和来源
- ✅ 及时发现数据缺失问题
- ✅ 数据流转过程可观测、可调试

---

## 相关文档

- [数据验证机制](./DATA_VALIDATION.md)
- [MCP 集成指南](../MCP_INTEGRATION_GUIDE.md)
