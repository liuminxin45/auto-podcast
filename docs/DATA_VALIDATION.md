# 数据验证机制

## 概述

为了防止"字段名不匹配"等静默失败问题，项目引入了多层数据验证机制，确保每个流程的数据完整性和正确性。

---

## 问题背景

### 静默失败的典型案例

```python
# ❌ 静默失败的代码
item["research_evidence"] = evidence.get("evidence_summary", "")
#                                        ^^^^^^^^^^^^^^^^  ^^
#                                        不存在的字段      默认空值
```

**问题**：
- `dict.get()` 找不到键时返回默认值，不抛异常
- 没有数据验证，无法发现字段名错误
- 日志只记录"合并成功"，不检查数据质量
- 结果：`enhanced_items.json` 中 `research_evidence` 为空，但流程显示"成功"

---

## 解决方案：多层防御机制

### 1. 数据验证工具模块 (`src/utils/validation.py`)

提供以下验证函数：

#### `validate_required_fields()`
验证字典是否包含所有必需字段。

```python
from src.utils.validation import validate_required_fields

result = validate_required_fields(
    data={"id": "123", "title": "test"},
    required_fields={"id", "title", "summary"},
    context="Item",
    strict=True
)

if not result.passed:
    # 错误：缺少必需字段: {'summary'}
    result.raise_if_failed(strict=True)
```

#### `validate_field_types()`
验证字段类型是否正确。

```python
from src.utils.validation import validate_field_types

result = validate_field_types(
    data={"id": "123", "confidence": "high"},  # confidence 应该是 float
    field_types={"id": str, "confidence": float},
    context="Evidence",
    strict=True
)

if not result.passed:
    # 错误：字段 'confidence' 类型错误: 期望 float, 实际 str
    result.raise_if_failed(strict=True)
```

#### `validate_evidence_pack()`
验证 EvidencePack 数据结构。

```python
from src.utils.validation import validate_evidence_pack

evidence_pack = {
    "item_id": "abc123",
    "claim": {...},
    "main_query": {...},
    "summary": "...",
    "verdict": "supported",
    "confidence": 0.85
}

result = validate_evidence_pack(evidence_pack, strict=True)
result.raise_if_failed(strict=True)
```

#### `validate_enhanced_item()`
验证 Enhanced Item 数据结构。

```python
from src.utils.validation import validate_enhanced_item

enhanced_item = {
    "id": "abc123",
    "title": "...",
    "research_evidence": "...",
    "research_claims": [...],
    "research_verdict": "supported",
    "research_confidence": 0.85
}

result = validate_enhanced_item(
    enhanced_item,
    require_research=True,
    strict=True
)
result.raise_if_failed(strict=True)
```

#### `validate_batch()`
批量验证数据列表。

```python
from src.utils.validation import validate_batch, validate_evidence_pack

result = validate_batch(
    items=evidence_packs,
    validator_func=validate_evidence_pack,
    context="Evidence Packs",
    fail_fast=False,  # 不在第一个错误时停止
    strict=True
)

result.raise_if_failed(strict=True)
```

---

### 2. ResearchStep 集成验证

#### 验证点 1：Evidence Packs 验证

在 `_merge_research_results()` 中验证 evidence_packs 结构：

```python
# 验证 evidence_packs
validation_result = validate_batch(
    evidence_packs,
    validate_evidence_pack,
    context="Evidence Packs",
    fail_fast=False,
    strict=strict_mode
)

if not validation_result.passed:
    if strict_mode:
        validation_result.raise_if_failed(strict=True)
    else:
        self.logger.warning("验证失败，但非严格模式，继续执行")
```

**检查内容**：
- ✅ `item_id` 字段存在且非空
- ✅ `claim` 字段存在且为字典
- ✅ `summary` 字段存在且为字符串
- ✅ `verdict` 字段存在且为字符串
- ✅ `confidence` 字段存在且为数字

#### 验证点 2：合并完整性检查

检查是否所有 items 都成功合并了 research 结果：

```python
if merged_count < len(ctx.items_selected):
    missing_count = len(ctx.items_selected) - merged_count
    self.logger.warning(
        f"警告: {missing_count} 个 items 没有匹配到 research 结果"
    )
    
    if strict_mode:
        raise ValidationError(
            f"严格模式: {missing_count} 个 items 缺少 research 结果，中止流程"
        )
```

#### 验证点 3：Enhanced Items 验证

在保存前验证 enhanced_items 结构：

```python
validation_result = validate_batch(
    ctx.items_selected,
    lambda item, strict: validate_enhanced_item(item, require_research=True, strict=strict),
    context="Enhanced Items",
    fail_fast=False,
    strict=strict_mode
)

if not validation_result.passed:
    if strict_mode:
        validation_result.raise_if_failed(strict=True)
```

**检查内容**：
- ✅ 基础字段：`id`, `title`, `source_name`
- ✅ Research 字段：`research_evidence`, `research_claims`, `research_verdict`, `research_confidence`
- ✅ 字段值非空（警告级别）

---

### 3. 严格模式配置

在 `config/base/settings.yaml` 中配置：

```yaml
research:
  provider: "bocha"
  enabled: true
  strict_validation: true  # 严格模式：数据验证失败时立即中止并抛出异常
```

**严格模式 (strict_validation: true)**：
- ✅ 缺少必需字段 → **抛出异常，中止流程**
- ✅ 字段类型错误 → **抛出异常，中止流程**
- ✅ 部分 items 缺少 research 结果 → **抛出异常，中止流程**
- ✅ 字段值为空 → **记录警告，继续执行**

**非严格模式 (strict_validation: false)**：
- ⚠️ 缺少必需字段 → **记录警告，继续执行**
- ⚠️ 字段类型错误 → **记录警告，继续执行**
- ⚠️ 部分 items 缺少 research 结果 → **记录警告，继续执行**

---

## 验证流程示意图

```
┌─────────────────────────────────────────────────────────────┐
│                    ResearchStep.execute()                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ResearchPipeline.run()                          │
│              返回: evidence_packs (list[dict])               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         【验证点 1】验证 Evidence Packs 结构                  │
│         validate_batch(evidence_packs, ...)                  │
│         ✓ item_id 存在？                                     │
│         ✓ claim 存在且为 dict？                              │
│         ✓ summary 存在且为 str？                             │
│         ✓ verdict 存在且为 str？                             │
│         ✓ confidence 存在且为 number？                       │
│                                                              │
│         如果失败 + strict_mode → 抛出 StrictModeError        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              合并 research 结果到 items_selected              │
│              merged_count = 4/4                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         【验证点 2】检查合并完整性                            │
│         merged_count < len(items_selected)?                  │
│                                                              │
│         如果是 + strict_mode → 抛出 ValidationError          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         【验证点 3】验证 Enhanced Items 结构                  │
│         validate_batch(items_selected, ...)                  │
│         ✓ id, title, source_name 存在？                      │
│         ✓ research_evidence 存在？                           │
│         ✓ research_claims 存在？                             │
│         ✓ research_verdict 存在？                            │
│         ✓ research_confidence 存在？                         │
│                                                              │
│         如果失败 + strict_mode → 抛出 StrictModeError        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              保存 enhanced_items.json                        │
│              ✓ 数据完整且正确                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 错误示例

### 示例 1：缺少必需字段

```python
evidence_pack = {
    "claim": {...},
    "summary": "..."
    # ❌ 缺少 item_id
}

# 严格模式下会抛出异常：
# StrictModeError: 严格模式验证失败:
# EvidencePack - 缺少必需字段: {'item_id'}
```

### 示例 2：字段类型错误

```python
evidence_pack = {
    "item_id": "abc123",
    "claim": {...},
    "summary": "...",
    "confidence": "high"  # ❌ 应该是 float，不是 str
}

# 严格模式下会抛出异常：
# StrictModeError: 严格模式验证失败:
# EvidencePack - 字段 'confidence' 类型错误: 期望 float, 实际 str
```

### 示例 3：部分 items 缺少 research 结果

```
Evidence packs 的 item_id: ['abc123', 'def456']
Items selected 的 ID: ['abc123', 'def456', 'ghi789']

# ❌ ghi789 没有匹配到 research 结果

# 严格模式下会抛出异常：
# ValidationError: 严格模式: 1 个 items 缺少 research 结果，中止流程
```

---

## 日志输出示例

### 成功场景

```
INFO - 开始验证 4 个 evidence packs (strict=True)
INFO - Evidence Packs - 验证 4 项数据
INFO - Evidence packs 的 item_id: ['abc123', 'def456', 'ghi789', 'jkl012']
INFO - Items selected 的 ID: ['abc123', 'def456', 'ghi789', 'jkl012']
INFO - 已将 4/4 个 items 的 research 结果合并
INFO - 开始验证 4 个 enhanced items (strict=True)
INFO - Enhanced Items - 验证 4 项数据
INFO - 增强后的 items 已保存: .../enhanced_items.json
```

### 失败场景（严格模式）

```
INFO - 开始验证 4 个 evidence packs (strict=True)
ERROR - Evidence Packs - 验证 4 项数据, 2 个错误
ERROR - [0] EvidencePack - 缺少必需字段: {'item_id'}
ERROR - [2] EvidencePack - 字段 'confidence' 类型错误: 期望 float, 实际 str
CRITICAL - StrictModeError: 严格模式验证失败:
[0] EvidencePack - 缺少必需字段: {'item_id'}
[2] EvidencePack - 字段 'confidence' 类型错误: 期望 float, 实际 str
```

### 失败场景（非严格模式）

```
INFO - 开始验证 4 个 evidence packs (strict=False)
WARNING - Evidence Packs - 验证 4 项数据, 2 个错误
WARNING - [0] EvidencePack - 缺少必需字段: {'item_id'}
WARNING - Evidence packs 验证失败，但非严格模式，继续执行
INFO - 已将 3/4 个 items 的 research 结果合并
WARNING - 警告: 1 个 items 没有匹配到 research 结果
INFO - 增强后的 items 已保存: .../enhanced_items.json
```

---

## 最佳实践

### 1. 开发阶段：启用严格模式

```yaml
research:
  strict_validation: true  # 立即发现问题
```

### 2. 生产环境：根据需求选择

- **关键业务流程**：启用严格模式，确保数据质量
- **容错性要求高**：禁用严格模式，记录警告但继续执行

### 3. 添加自定义验证

```python
from src.utils.validation import ValidationResult

def validate_custom_data(data: dict, strict: bool = True) -> ValidationResult:
    errors = []
    warnings = []
    
    # 自定义验证逻辑
    if "custom_field" not in data:
        errors.append("缺少 custom_field")
    
    if data.get("custom_value", 0) < 0:
        warnings.append("custom_value 为负数")
    
    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

### 4. 在其他 Step 中集成验证

```python
from src.utils.validation import validate_batch, ValidationError

class MyStep(BaseStep):
    def execute(self, ctx):
        # ... 处理数据 ...
        
        # 验证数据
        strict_mode = ctx.config.get("my_step", {}).get("strict_validation", True)
        
        result = validate_batch(
            my_data,
            my_validator,
            context="My Data",
            strict=strict_mode
        )
        
        if not result.passed and strict_mode:
            result.raise_if_failed(strict=True)
```

---

## 总结

通过引入多层数据验证机制，项目现在能够：

✅ **及时发现问题**：字段名不匹配、类型错误等问题会立即被发现  
✅ **明确错误信息**：详细的错误消息指出具体问题和位置  
✅ **可配置的严格程度**：根据场景选择严格模式或容错模式  
✅ **防止静默失败**：关键数据缺失会触发异常，而不是返回空值  
✅ **提高代码质量**：强制开发者关注数据完整性

这套机制确保了 pipeline 各阶段的数据质量，避免了"看起来成功，实际失败"的情况。
