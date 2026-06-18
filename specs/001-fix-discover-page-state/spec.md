# 能力规格说明: 修复发现页节目状态与交互问题

**Feature Directory**: `specs/001-fix-discover-page-state`
**创建时间**: 2026-06-18
**状态**: Draft
**用户输入**: 使用 spec-kit 工作流修复发现页新节目状态污染、立即采集 loading、返回按钮图标、LLM 依赖开关、console 刷屏和雷达设置图标问题。

## L1 Artifact Contract

- **Layer**: L1 Business Specification
- **Purpose**: capture observable behavior, user/business expectations,
  compatibility boundaries, assumptions, and validation expectations.
- **Required sections**: `人类审核摘要`, `能力概览`, `分流摘要`, `Workspace Repository Map`,
  `能力场景`, `功能需求`, `兼容性与集成边界`, `验证预期`, `非目标`, `假设`, `待确认问题`.
- **Structured state**: `.specify/feature.json` and `workflow-state.json` carry
  workflow metadata; do not encode routing state only in prose.
- **Next layer**: L2 `plan.md` must cite this spec and preserve unresolved
  questions as plan risks or blockers.

## 人类审核摘要

- **一句话结论**: 修复发现页在节目切换和无配置场景下的状态、loading、提示、日志与图标表现，使新节目从干净状态开始。
- **重点审核**: 新节目不能继承旧新闻；采集 loading 必须闭环；依赖 LLM 的“智能标签”等入口必须在未配置时提示用户去设置。
- **改动范围**: `src/components/DiscoverPanel.tsx`、节目/工作流状态相关前端路径，必要时涉及 Electron workflow state 读取与配置查询。
- **不涉及 / N/A 汇总**: N/A Public SDK、NativePlugin、真实设备、Qt 迁移；这是 Electron/React 前端与本地 workflow state bugfix。
- **主要风险**: medium；发现页已有较多本地状态和 workflow state 同步逻辑，修复必须避免清掉当前节目真实数据。
- **验收入口**: 创建新节目、进入发现页、清空素材、点击立即采集、切换智能标签、检查控制台；运行 `npm run verify`、`npm run build`，可选 `npm run acceptance:cdp`。
- **当前状态 / 下一步**: Ready for plan/implement；无阻塞澄清。
- **必需人工决策**: N/A，用户已明确期望行为。

## 能力概览

发现页必须以当前打开节目为唯一真相源。新建节目时，发现页不得显示上一个节目的“新闻”或素材列表；采集动作必须有成功、失败和取消/结束态；依赖 LLM 的 UI 开关在缺少模型配置时不得静默启用；可见按钮、图标和提示必须与中文文案一致；清空新闻后不得持续刷控制台日志。

## 分流摘要

**Task Type**: bugfix
**Routing Confidence**: high
**Risk Level**: medium
**Delivery Profile**: standard-bugfix
**Intake Source**: user message
**关键分流依据**:

- 用户提供了明确的实际行为和期望行为，集中在发现页状态隔离、按钮 loading、UI 文案/图标、LLM 配置依赖和日志噪声。
- 涉及 UI 状态同步和运行时行为，不应作为 micro-fix 直接跳过规格与验证。

## Workspace Repository Map

**workspace_root**: `E:\Neo\auto-podcast`
**default_base_branch**: `main`
**repository_map**: `.specify/memory/repository-map.md`

| Repository | Path | Role | Capability / Ownership | Why affected / N/A |
|------------|------|------|-------------------------|--------------------|
| `auto-podcast` | `.` | `electron-react-python-podcast-workbench` | Electron desktop shell, React/Vite authoring UI, Python podcast workflow nodes, shared state/config protocol, TrendRadar bridge, build/test scripts, docs, and runtime output conventions. | 发现页和节目状态属于 React/Electron 工作台主路径。 |

## 能力场景

### CS1 - 新节目发现页状态隔离 (Priority: P1)

**目标**: 新增节目后打开发现页时，素材、新闻、选中项和发现状态均来自新节目，不继承旧节目。

**优先级理由**: 状态污染会导致用户误以为新节目已有素材，是最核心的数据正确性问题。

**独立验证**: 在旧节目发现页存在素材后新增节目，打开新节目发现页，确认列表为空或仅显示新节目的真实 state。

**验收场景**:

1. **Given** 旧节目发现页已有“新闻”素材，**When** 新增并打开一个节目，**Then** 新节目发现页不显示旧节目素材。
2. **Given** 新节目没有任何采集结果，**When** 进入发现页，**Then** 页面显示中文空状态，不显示旧节目计数或选中状态。

### CS2 - 立即采集 loading 闭环 (Priority: P1)

**目标**: 点击“立即采集”后，按钮 loading 必须在采集成功、失败或无结果后结束，并展示真实结果或错误提示。

**优先级理由**: 无限转圈阻断发现页主路径。

**独立验证**: 点击“立即采集”，观察按钮状态和列表/错误提示，确认不会永久 loading。

**验收场景**:

1. **Given** 发现页可运行采集，**When** 点击“立即采集”，**Then** 采集结束后按钮恢复可点击。
2. **Given** 采集失败或返回空结果，**When** 点击“立即采集”，**Then** 按钮恢复可点击并显示明确中文提示。

### CS3 - LLM 依赖能力的正确引导 (Priority: P1)

**目标**: “智能标签”等依赖 LLM 的开关在未配置 LLM 时不能静默开启，必须提示用户配置智能能力。

**优先级理由**: 未配置也能开启会制造虚假能力，后续流程不可预测。

**独立验证**: 清空或缺失 LLM 配置时点击“智能标签”，确认开关不启用并显示设置引导。

**验收场景**:

1. **Given** 未配置 LLM API Key/API Base/model，**When** 用户开启“智能标签”，**Then** 系统阻止启用并提示去设置。
2. **Given** LLM 配置可用，**When** 用户开启“智能标签”，**Then** 开关允许启用。

### CS4 - 发现页 UI 文案、图标与日志噪声修复 (Priority: P2)

**目标**: “返回”按钮图标与语义一致；雷达设置使用设置图标；清空新闻后不持续刷控制台。

**优先级理由**: 这些问题影响可信度和调试效率，但不直接破坏数据主路径。

**独立验证**: 浏览发现页和其它弹层/页面头部，确认返回按钮不再使用 `X` 语义；清空新闻后控制台不持续输出相同 `fetchContents` 日志。

**验收场景**:

1. **Given** 发现页或其它工作台顶部显示“返回”，**When** 观察按钮图标，**Then** 图标表达返回而不是关闭。
2. **Given** 发现页已清空新闻，**When** 页面空闲，**Then** 控制台不持续重复输出 `fetchContents: 0`。

## 功能需求

- **FR-001**: 系统必须在打开或新建节目时按当前节目 ID 初始化发现页状态，不能复用上一个节目的列表、选中项、标签状态或本地缓存。
- **FR-002**: 系统必须确保“立即采集”按钮的 loading 状态在采集成功、失败、空结果或异常后结束。
- **FR-003**: 系统必须把采集失败、无后端、无数据或配置缺失显示为明确中文提示，不得表现为永久加载。
- **FR-004**: 系统必须在未配置 LLM 时阻止启用依赖 LLM 的发现页能力，并提供设置引导。
- **FR-005**: 系统必须审查发现页内类似“智能标签”的配置依赖入口，避免无配置也可开启的虚假状态。
- **FR-006**: 系统必须将文案为“返回”的按钮图标改为返回语义，并检查其它工作台是否存在相同问题。
- **FR-007**: 系统必须将发现页雷达设置按钮换成设置语义图标。
- **FR-008**: 系统必须停止清空新闻后重复刷 `DiscoverPanel fetchContents` console 日志。
- **FR-LAYERING**: N/A；本任务不涉及 `ServiceBridge`、`CoreRuntime` 或设备运行态边界。

## 兼容性与集成边界

- **Public SDK/API**: N/A；不修改公共 API。
- **NativePlugin / ServiceBridge Bridge Contract**: N/A；本项目为 Electron/React/Python 工作台。
- **HostApplication / Plugin Contract**: N/A；不涉及插件宿主合同。
- **Frontend State/UI Contract**: 发现页本地 state 必须以当前节目 workflow state 为边界，节目切换时重置或重新派生。
- **UI Display Contract**: UI 文案、图标、开关状态必须反映真实能力状态。
- **UI Interaction Display Contract**: 依赖 LLM 的交互必须基于配置可用性决定启用/禁用或拦截提示。
- **Device/Runtime Contract**: N/A；不涉及设备。
- **Encoding/Localization Boundary**: 中文可见提示必须保持 UTF-8 文本，不引入乱码。

## Identity / State / API Boundary

N/A；本任务不涉及设备身份、SDK native id、UUID 或跨 Libs/Biz/UI 设备身份边界。节目 ID 和 workflow ID 仅作为本项目现有 Electron workflow state 标识使用。

## Qt 源行为覆盖清单

N/A；本任务不是 Qt 迁移。

## UI 设计来源目录

| 目录类型 | Path | 说明 |
|----------------|------|-------|
| Original Qt UI/source | N/A | 不是 Qt 迁移。 |
| Product design/mockup/export | 用户本轮明确需求 | 用户明确要求返回图标、设置图标和 LLM 引导行为。 |
| Target frontend/plugin | `src/components/DiscoverPanel.tsx`、`src/App.tsx`、相关页面组件 | 发现页与工作台页面实现目标。 |
| Shared assets/icons/screenshots | N/A | 使用现有 Ant Design/lucide 或项目已有图标体系。 |

## UI / UX / 文案依据追踪

| Target UI element / copy | Reliable source | Expected implementation | Intentional delta / approval |
|--------------------------|-----------------|-------------------------|------------------------------|
| “返回”按钮 | 用户明确指出“明明是返回，但按钮是 X” | 使用返回语义图标，tooltip/文案保持中文 | 用户要求修复 |
| “智能标签”开关 | 用户明确指出未配置 LLM 不应可开启 | 未配置时阻止启用并显示配置引导 | 用户要求修复 |
| 雷达设置按钮 | 用户明确要求“换个设置的 SVG 图标” | 改为设置语义图标 | 用户要求修复 |
| 清空新闻后的 console 日志 | 用户提供控制台日志 | 移除或限制重复 debug log | 用户要求修复 |

## 影响模块

- `src/components/DiscoverPanel.tsx`: 发现页素材状态、采集按钮、智能标签、雷达设置、console 日志。
- `src/App.tsx` 及页面容器组件: 返回按钮图标检查与统一修复。
- `electron/main.js` / `electron/preload.js`: 如发现采集 loading 与 IPC 返回契约相关，需要保持错误返回可恢复。
- `scripts/run_cdp_acceptance.js` / `electron/acceptanceRunner.js`: 如 CDP 自验收需覆盖新行为，可补充或复用现有验收。

## 验证预期

- **Test-Case Plan Review**: approved-by-ai-obvious；用户给出明确 UI bug 和可复现路径。
- **Quality Vision**: 基于用户明确 UI 反馈和现有目标前端约定；不需要额外设计稿。
- **Acceptance Rubric**: 计划阶段生成，覆盖状态隔离、loading 闭环、LLM 引导、图标和日志。
- **Build**: `npm run build`。
- **Automated Tests**: `npm run verify`；如能低成本增加前端/脚本测试则补充，否则记录为 UI smoke。
- **Runtime/UI Smoke**: 启动应用后通过 CDP 或浏览器验证发现页主路径。
- **Device Validation**: N/A。
- **Downstream Check**: N/A。
- **AI Self-Acceptance**: 需要至少包含发现页新节目状态隔离、立即采集 loading 不永久、无 LLM 配置提示、console 不刷屏的证据。

## 非目标

- 不新增新的外部信息源。
- 不重做发现页整体视觉设计。
- 不修改 TrendRadar 外部项目主体逻辑。
- 不引入新的 LLM provider 或音频 provider。
- 不改变发布、写作、制作等非发现页主流程语义，除非是统一修复“返回”图标。

## 假设

- 当前 UI 使用 Ant Design 图标体系，可用返回和设置语义图标替换不匹配图标。
- “智能标签”依赖 LLM 指文本模型配置，而非仅本地规则。
- 新节目应完全隔离旧节目发现页本地 state 和 workflow state。

## 待确认问题

- N/A；用户需求足够具体，无阻塞澄清。
