# 节点测试文档

本文档说明如何使用 mock 数据测试所有节点的功能。

## 测试架构

每个节点都有独立的测试模块，使用标准化的 mock 数据验证功能：

```
nodes/
├── fetch/
│   ├── node.py          # 节点实现
│   ├── config.py        # 配置类
│   └── test.py          # 测试模块 ✨
├── preprocess/
│   └── test.py          # 测试模块 ✨
└── [其他 9 个节点...]
```

## 快速开始

### 运行所有节点测试

```bash
npm run test:nodes
# 或
python scripts/test_all_nodes.py
```

### 运行单个节点测试

```bash
# 测试 fetch 节点
python nodes/fetch/test.py

# 测试 preprocess 节点
python nodes/preprocess/test.py

# 测试任意节点
python nodes/<node_name>/test.py
```

## Mock 数据工厂

所有测试使用 `tests/mock_data.py` 中的标准化 mock 数据：

### 核心函数

```python
from tests.mock_data import (
    create_base_state,              # 创建基础状态
    create_state_for_node,          # 为特定节点创建状态
    create_mock_raw_contents,       # 原始内容
    create_mock_cleaned_contents,   # 清洗后内容
    create_mock_script,             # 播客脚本
    create_mock_stages,             # 对话分段
    # ... 更多工厂函数
)
```

### 使用示例

```python
# 为 preprocess 节点创建测试状态
state = create_state_for_node("preprocess")
# state 会自动包含 raw_contents 字段

# 运行节点
from nodes.preprocess.node import run
from nodes.preprocess.config import PreprocessConfig

config = PreprocessConfig()
result = run(state, config)

# 验证输出
assert "cleaned_contents" in result
assert len(result["cleaned_contents"]) > 0
```

## 测试结构

每个节点的测试文件遵循统一结构：

```python
"""Test module for <node_name> node"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.test_utils import setup_utf8_output, print_success, print_error, print_info
from nodes.<node_name>.node import run
from nodes.<node_name>.config import <NodeConfig>
from tests.mock_data import create_state_for_node

setup_utf8_output()  # Windows 编码兼容


def test_<node_name>_node():
    """Test <node_name> node with mock data"""
    print_info("Testing <node_name> node...")
    
    # 1. 准备测试状态
    state = create_state_for_node("<node_name>")
    
    # 2. 配置节点
    config = <NodeConfig>(...)
    
    # 3. 运行节点
    result = run(state, config)
    
    # 4. 验证输出
    assert "expected_field" in result
    assert len(result["expected_field"]) > 0
    
    print_success("Test passed!")
    return True


if __name__ == "__main__":
    try:
        test_<node_name>_node()
        sys.exit(0)
    except AssertionError as e:
        print_error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

## 各节点测试说明

### 1. Fetch 节点
- **输入**: 空状态
- **输出**: `raw_contents` (原始抓取内容)
- **验证**: 内容列表非空，每项包含 title/content/url

### 2. Preprocess 节点
- **输入**: `raw_contents`
- **输出**: `cleaned_contents` (清洗后内容)
- **验证**: 过滤短内容，保留符合长度要求的内容

### 3. Research 节点
- **输入**: `cleaned_contents`
- **输出**: `researched_contents` (研究扩展后内容)
- **验证**: 内容数量一致，可能添加研究摘要

### 4. Topic Selection 节点
- **输入**: `researched_contents`
- **输出**: `selected_topic`, `selected_materials`
- **验证**: 选定主题和素材

### 5. Script 节点
- **输入**: `selected_topic`, `selected_materials`
- **输出**: `script` (播客脚本)
- **验证**: 脚本包含 title/dialogue，对话列表非空

### 6. Stages 节点
- **输入**: `script`
- **输出**: `stages` (对话分段)
- **验证**: 每个对话行对应一个 stage，包含 order/speaker/text

### 7. TTS 节点
- **输入**: `stages`
- **输出**: `audio_segments` (音频片段路径列表)
- **验证**: 音频文件路径列表，每个路径以 .mp3 结尾

### 8. Audio Postprocess 节点
- **输入**: `audio_segments`
- **输出**: `final_audio_path`, `audio_metadata`
- **验证**: 最终音频文件路径和元数据

### 9. Assets 节点
- **输入**: `script`, `final_audio_path`
- **输出**: `cover_path` (封面图片路径)
- **验证**: 封面文件路径 (.jpg 或 .png)

### 10. Store 节点
- **输入**: `final_audio_path`, `cover_path`, `script`
- **输出**: `storage_info` (存储信息)
- **验证**: 存储路径信息字典

### 11. Publish 节点
- **输入**: `storage_info`, `script`
- **输出**: `rss_path`, `publish_status`
- **验证**: RSS 文件路径 (.xml) 和发布状态

## 测试工具

### test_utils.py

提供跨平台兼容的输出函数：

```python
from tests.test_utils import (
    setup_utf8_output,    # 设置 UTF-8 输出（Windows 必需）
    print_success,        # 打印成功消息
    print_error,          # 打印错误消息
    print_info            # 打印信息消息
)
```

### 测试运行器

`scripts/test_all_nodes.py` 提供批量测试功能：

- 并发运行所有节点测试
- 统一输出格式
- 汇总测试结果
- 超时保护（30秒/节点）

## 添加新节点测试

1. **创建测试文件**: `nodes/<new_node>/test.py`

2. **在 mock_data.py 中添加工厂函数**:
```python
def create_state_for_node(node_name: str):
    # ...
    if node_name == "new_node":
        state["required_input"] = create_mock_input()
        return state
```

3. **编写测试函数**:
```python
def test_new_node_node():
    state = create_state_for_node("new_node")
    config = NewNodeConfig()
    result = run(state, config)
    
    assert "expected_output" in result
    print_success("Test passed!")
    return True
```

4. **更新测试运行器**:
在 `scripts/test_all_nodes.py` 的 `NODES` 列表中添加 `'new_node'`

5. **运行测试**:
```bash
python nodes/new_node/test.py
npm run test:nodes
```

## 持续集成

测试命令已集成到 package.json：

```json
{
  "scripts": {
    "test:nodes": "python scripts/test_all_nodes.py",
    "test:integration": "python scripts/integration_test.py",
    "test": "npm run test:nodes && npm run test:integration"
  }
}
```

建议在 CI/CD 流程中运行：

```bash
npm install
npm run test
```

## 故障排除

### Windows 编码问题

如果遇到 `UnicodeEncodeError`：

1. 确保测试文件开头调用 `setup_utf8_output()`
2. 使用 `print_success/print_error` 而不是直接 `print()`
3. 测试运行器已配置 `encoding='utf-8', errors='replace'`

### 测试失败调试

```bash
# 单独运行失败的节点测试，查看详细错误
python nodes/<failed_node>/test.py

# 查看完整输出
python -u nodes/<failed_node>/test.py
```

### Mock 数据不匹配

如果节点期望的输入格式与 mock 数据不符：

1. 检查 `tests/mock_data.py` 中的工厂函数
2. 更新 `create_state_for_node()` 为该节点提供正确的输入
3. 确保 mock 数据结构与节点实现一致

## 最佳实践

1. **独立性**: 每个测试应该独立运行，不依赖其他测试
2. **Mock 优先**: 使用 mock 数据而不是真实 API 调用
3. **快速执行**: 单个测试应在 1 秒内完成
4. **清晰断言**: 使用明确的断言消息
5. **错误处理**: 测试应捕获并报告所有异常

## 测试覆盖

当前测试覆盖：

- ✅ 所有 11 个节点的基本功能测试
- ✅ Mock 数据输入/输出验证
- ✅ 配置类实例化
- ✅ 状态字段存在性检查
- ⚠️ 边界条件测试（待补充）
- ⚠️ 错误处理测试（待补充）
- ⚠️ 性能测试（待补充）

## 相关文档

- [架构规范](./ARCHITECTURE.md) - 节点设计原则
- [UI/UX 设计](./UI_UX_DESIGN.md) - 前端设计文档
- [README](../README.md) - 项目总览
