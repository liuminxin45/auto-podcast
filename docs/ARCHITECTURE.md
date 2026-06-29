# PodFlow Studio 架构规范

## 核心原则

### 1. 模块解耦性（最高优先级）

**每个节点必须完全独立**：
- 每个节点在独立目录：`nodes/<node_name>/`
- 每个节点包含：
  - `config.py`：配置类（继承 `NodeConfigBase`）
  - `node.py`：核心逻辑（导出 `run()` 函数）
  - `__init__.py`：包初始化（可为空）
- **禁止**节点之间直接导入对方的代码
- **禁止**节点访问其他节点的内部实现

### 2. 接口规范

所有节点必须遵循统一接口：

```python
def run(state: Dict[str, Any], config: NodeConfig = None) -> Dict[str, Any]:
    """
    Args:
        state: 完整的 pipeline 状态字典
        config: 节点配置对象（可选，默认使用 default）
    
    Returns:
        更新后的 state 字典
    """
    pass
```

**接口约定**：
- 输入：只读取 state 中本节点需要的字段
- 输出：只修改 state 中本节点负责的字段
- 日志：通过 `state["logs"]` 追加日志
- 错误：通过 `state["errors"]` 追加错误信息
- **禁止**修改不属于本节点职责的字段

### 3. 配置管理

所有配置类必须：
- 继承 `protocol.config_base.NodeConfigBase`（Pydantic 验证）
- 提供合理的默认值
- 支持 `from_dict()` 从字典创建
- 字段使用 `Field()` 添加描述和验证规则

```python
from protocol.config_base import NodeConfigBase
from pydantic import Field

class FetchConfig(NodeConfigBase):
    sources: List[Dict[str, str]] = Field(
        default_factory=lambda: [{"type": "rss", "url": "..."}],
        description="Data sources to fetch from"
    )
    max_items: int = Field(default=10, ge=1, le=100)
```

### 4. 状态管理

**PodcastState 字段职责划分**：

| 字段 | 负责节点 | 说明 |
|------|----------|------|
| `raw_contents` | fetch | 原始抓取内容 |
| `cleaned_contents` | preprocess | 清洗后内容 |
| `researched_contents` | research | 研究扩展后内容 |
| `selected_topic` | topic_selection | 选定的主题 |
| `selected_materials` | topic_selection | 选定的素材 |
| `script` | script, script_refine | 播客脚本 |
| `stages` | stages | 分段信息 |
| `audio_segments` | tts | 音频片段路径 |
| `final_audio_path` | audio_postprocess | 最终音频 |
| `cover_path` | assets | 封面图片 |
| `storage_info` | store | 存储信息 |
| `rss_path` | publish | RSS 文件路径 |

**规则**：
- 每个字段只能由一个节点写入
- 其他节点只能读取
- 修改字段前必须检查前置节点是否已填充

### 5. 错误处理

```python
def run(state: Dict[str, Any], config: Config = None) -> Dict[str, Any]:
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    logs.append(f"[{NodeName}] Starting...")
    
    try:
        # 核心逻辑
        result = do_work()
        state["output_field"] = result
        logs.append(f"[{NodeName}] Success")
    except Exception as e:
        errors.append({
            "node": "node_name",
            "message": str(e),
            "detail": traceback.format_exc()
        })
        logs.append(f"[{NodeName}] Failed: {e}")
    
    state["logs"] = logs
    state["errors"] = errors
    return state
```

**规则**：
- 所有异常必须捕获，不能让节点崩溃
- 错误信息必须包含 `node`、`message`、`detail`
- 发生错误后仍然返回 state（让后续节点决定是否继续）

### 6. 测试规范

每个节点必须：
- 在 `tests/test_nodes.py` 中有独立测试函数
- 使用 `tests/mock_data.py` 中的标准 mock 数据
- 测试覆盖：正常流程、边界情况、错误处理

```python
def test_my_node():
    from nodes.my_node.node import run
    from nodes.my_node.config import MyNodeConfig
    
    state = copy.deepcopy(MOCK_INPUT_STATE)
    config = MyNodeConfig()
    result = run(state, config)
    
    assert result["output_field"] is not None
    assert len(result["errors"]) == 0
```

### 7. 依赖管理

**允许的依赖**：
- `protocol/state.py`：状态定义
- `protocol/config_base.py`：配置基类
- 标准库和 `requirements.txt` 中的第三方库

**禁止的依赖**：
- 其他节点的代码
- `orchestrator/` 中的代码
- 全局单例或共享状态

### 8. 目录结构

```
PodFlow Studio/
├── protocol/              # 共享协议（state、config base）
│   ├── state.py
│   └── config_base.py
├── nodes/                 # 所有节点（完全独立）
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── node.py
│   ├── preprocess/
│   └── .../
├── orchestrator/          # 流程编排（LangGraph）
│   └── graph.py
├── tests/                 # 测试
│   ├── mock_data.py
│   ├── test_nodes.py
│   └── run_tests.py
├── docs/                  # 文档
│   ├── ARCHITECTURE.md    # 本文档
│   └── ...
├── main.py                # CLI 入口
├── studio.py              # LangGraph Studio 入口
└── langgraph.json         # Studio 配置
```

### 9. 新增节点 Checklist

添加新节点时必须：

- [ ] 创建 `nodes/<name>/` 目录
- [ ] 创建 `config.py`（继承 `NodeConfigBase`）
- [ ] 创建 `node.py`（实现 `run()` 函数）
- [ ] 在 `orchestrator/graph.py` 中注册节点
- [ ] 在 `protocol/state.py` 中添加输出字段（如需要）
- [ ] 在 `tests/mock_data.py` 中添加 mock 数据
- [ ] 在 `tests/test_nodes.py` 中添加测试
- [ ] 更新 `docs/ARCHITECTURE.md` 的字段职责表

### 10. 代码审查要点

提交代码前检查：

- [ ] 节点是否完全独立？（无跨节点导入）
- [ ] 接口是否符合 `run(state, config) -> state`？
- [ ] 配置类是否继承 `NodeConfigBase`？
- [ ] 错误是否正确捕获和记录？
- [ ] 是否有对应的测试用例？
- [ ] 日志是否清晰（`[NodeName] action`）？
- [ ] 是否只修改了本节点负责的字段？

---

## 为什么这样设计？

### 解耦性优先

**问题**：之前的代码耦合严重，改一个节点影响其他节点，难以维护。

**解决**：
- 每个节点独立目录，清晰边界
- 统一接口，节点之间通过 state 通信
- 禁止跨节点依赖

### 可视化调试

**问题**：需要在 LangGraph Studio 中实时查看流程。

**解决**：
- 使用 LangGraph 作为编排框架
- 所有节点在同一进程，Studio 可以完整追踪
- 日志和错误统一记录在 state 中

### 易扩展

**问题**：添加新功能需要改动多处代码。

**解决**：
- 新增节点只需创建独立目录
- 在 `orchestrator/graph.py` 中注册即可
- 不影响现有节点

### 易测试

**问题**：节点之间依赖导致测试困难。

**解决**：
- 每个节点可以独立测试
- 使用标准 mock 数据
- 测试覆盖率清晰

---

## 反模式（禁止）

❌ **跨节点导入**
```python
# 错误
from nodes.fetch.node import _fetch_rss
```

❌ **修改不属于自己的字段**
```python
# 错误：preprocess 节点修改 script
state["script"] = {"title": "..."}
```

❌ **全局状态**
```python
# 错误
GLOBAL_CACHE = {}
```

❌ **硬编码配置**
```python
# 错误
def run(state):
    api_key = "<api-key>"  # 应该从 config 读取
```

❌ **未捕获异常**
```python
# 错误
def run(state):
    result = api_call()  # 可能抛异常但未捕获
    return state
```

---

遵循此规范，确保项目长期可维护、易扩展、易调试。
