# 能力规格说明: NewsNow 固定版本安装与自定义采集能力部署

**Feature Directory**: `specs/002-newsnow-pinned-install`
**创建时间**: 2026-06-25
**状态**: Draft
**用户输入**: 本地 NewsNow 在 `engine/newsnow is not cloned` 时需要现场拉取部署；希望在 `npm install` 时拉取固定提交/版本，并应用本项目额外自定义的数据采集能力。

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

- **一句话结论**: `npm install` 必须可自动准备本地 NewsNow 外部引擎到锁定版本，并重复应用 Auto-Podcast 自定义采集扩展。
- **重点审核**: 固定版本来源以 `engine/newsnow.lock.json` 为准；`engine/newsnow/` 仍是外部克隆目录，不入库；自定义采集能力必须作为仓库内可审计 overlay 或脚本输入存在。
- **改动范围**: `scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`package.json` postinstall 流程、`engine/newsnow.lock.json` 和新增 overlay/说明文件。
- **不涉及 / N/A 汇总**: 不改 Electron IPC 语义、不改 UI、不改 TrendRadar Python 采集算法、不把 NewsNow 上游源码提交入库。
- **主要风险**: 网络、GitHub 可达性、Node/pnpm 环境、上游目录结构变化会影响安装；脚本必须给出明确失败原因。
- **验收入口**: `npm install`、`npm run sync:newsnow`、`npm run check:newsnow` 应证明 clone、锁定提交和 overlay 状态。
- **当前状态 / 下一步**: Ready for plan；无阻塞澄清，继续进入实现计划。
- **必需人工决策**: N/A，本次固定提交来源已有 `engine/newsnow.lock.json`。

## 能力概览

项目依赖本地 NewsNow 作为 TrendRadar 的可自托管数据源。当前 `engine/newsnow/` 可能只存在半初始化 git 目录或完全缺失，运行时状态会显示 `engine/newsnow is not cloned`。本能力要求安装流程可自动从上游仓库拉取固定提交，校验本地目录真实可用，并在同步后应用 Auto-Podcast 维护的自定义采集能力，避免手动补目录、手动 patch 或依赖未记录的本地状态。

## 分流摘要

**Task Type**: new-feature
**Routing Confidence**: high
**Risk Level**: medium
**Delivery Profile**: standard-bugfix
**Intake Source**: 用户消息
**关键分流依据**:

- 这是安装/工具链能力扩展，不是 UI 修复或 Qt 迁移。
- 影响 `npm install`、NewsNow 外部引擎同步、运行时状态检查和外部目录 overlay。
- 需要命令级验证，不需要 CDP UI 验证。

## Workspace Repository Map

**workspace_root**: `E:\Neo\auto-podcast`
**default_base_branch**: `main`
**repository_map**: `.specify/memory/repository-map.md`

| Repository | Path | Role | Capability / Ownership | Why affected / N/A |
|------------|------|------|-------------------------|--------------------|
| `auto-podcast` | `.` | `electron-react-python-podcast-workbench` | Electron desktop shell, React/Vite authoring UI, Python podcast workflow nodes, shared state/config protocol, TrendRadar bridge, build/test scripts, docs, and runtime output conventions. | 需要修改脚本、安装流程和外部引擎锁定/overlay 规则。 |

## 能力场景 *(必填)*

### CS1 - 缺失或半初始化 NewsNow 时自动准备本地引擎 (Priority: P1)

**目标**: `npm install` 或 `npm run sync:newsnow` 能把 `engine/newsnow` 准备到可运行源码状态。

**优先级理由**: 没有本地 NewsNow 时，发现页本地数据源和 TrendRadar 自托管路径无法使用。

**独立验证**: 删除或清空 `engine/newsnow` 后运行同步命令，检查 `package.json` 存在、git HEAD 等于锁定 commit。

**验收场景**:

1. **Given** `engine/newsnow` 不存在，**When** 执行 `npm install`，**Then** 脚本克隆 `engine/newsnow.lock.json` 指定仓库并 checkout 指定 commit。
2. **Given** `engine/newsnow` 是无 HEAD 的半初始化 git 目录，**When** 执行 `npm run sync:newsnow`，**Then** 脚本能恢复为完整工作树，而不是继续报告目录已存在但不可用。
3. **Given** `engine/newsnow` 有未提交本地改动，**When** 执行同步，**Then** 默认拒绝覆盖并输出明确错误，除非使用显式覆盖/重置参数。

### CS2 - 同步后应用 Auto-Podcast 自定义采集扩展 (Priority: P1)

**目标**: Auto-Podcast 额外维护的数据采集能力能在每次同步后被重复应用到 NewsNow 工作树。

**优先级理由**: 自定义能力如果只存在于忽略目录，换机、清理目录或重新 clone 后会丢失。

**独立验证**: 同步后检查 overlay manifest 中声明的文件已出现在 `engine/newsnow`，并有可机读状态标记。

**验收场景**:

1. **Given** NewsNow 已 checkout 到锁定 commit，**When** 同步脚本结束，**Then** overlay 文件被复制到目标路径并记录 overlay 状态。
2. **Given** overlay 目标路径的父目录不存在，**When** 应用 overlay，**Then** 脚本创建目录并复制文件。
3. **Given** overlay 与上游文件冲突，**When** 未显式允许覆盖，**Then** 脚本输出冲突路径并失败。

### CS3 - 运行时状态能区分 clone、依赖和 overlay 问题 (Priority: P2)

**目标**: `npm run check:newsnow` 返回的状态能说明当前 NewsNow 缺什么。

**优先级理由**: 用户需要知道是未 clone、依赖未安装、Node/pnpm 不满足，还是自定义 overlay 未应用。

**独立验证**: 在不同缺失状态下执行 `npm run check:newsnow`，检查 JSON 字段和 blocker 文案。

**验收场景**:

1. **Given** 工作树缺少 `package.json`，**When** 执行状态检查，**Then** blocker 指向未完成 clone。
2. **Given** 工作树存在但 overlay 未应用，**When** 执行状态检查，**Then** blocker 指向自定义采集能力未部署。

## 功能需求 *(必填)*

- **FR-001**: 系统必须以 `engine/newsnow.lock.json` 的 `repo`、`commit`、`version` 作为默认 NewsNow 同步来源。
- **FR-002**: `npm install` 必须触发 NewsNow 同步流程，使缺失或半初始化的 `engine/newsnow` 变成完整源码工作树。
- **FR-003**: 同步脚本必须校验本地 HEAD 与锁定 commit；不一致时按锁定版本恢复，除非显式选择更新。
- **FR-004**: 同步脚本必须支持把仓库内维护的 Auto-Podcast 自定义采集 overlay 应用到 `engine/newsnow`。
- **FR-005**: overlay 的来源、目标路径和版本必须可审计，不能只依赖被 `.gitignore` 排除的本地文件。
- **FR-006**: `npm run check:newsnow` 必须报告 clone 可用性、锁定 commit、本地 commit、依赖安装状态、构建状态和 overlay 状态。
- **FR-007**: 遇到网络失败、git 不可用、目标目录脏改、Node/pnpm 不满足或 overlay 冲突时，脚本必须失败并输出明确 blocker。
- **FR-LAYERING**: N/A，本任务不涉及 UI 状态、ServiceBridge、CoreRuntime 或设备运行态边界。

## 兼容性与集成边界

- **Public SDK/API**: N/A，不涉及 SDK。
- **Script / CLI Contract**: 影响 `scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`npm run sync:newsnow`、`npm run check:newsnow`、`npm install` postinstall。
- **NativePlugin / ServiceBridge Bridge Contract**: N/A，不涉及插件桥。
- **HostApplication / Plugin Contract**: N/A，不涉及宿主插件协议。
- **Frontend State/UI Contract**: N/A，不改 UI 状态。
- **UI Display Contract**: N/A，无可见 UI 变化。
- **UI Interaction Display Contract**: N/A，无 UI 交互变更。
- **Device/Runtime Contract**: N/A，不涉及设备或采集硬件运行态。
- **Encoding/Localization Boundary**: 脚本输出可包含中文提示，但 JSON 状态字段保持 ASCII key。

## Identity / State / API Boundary

N/A，本任务不涉及设备身份、设备列表、连接状态、RPC/N-API 或 public API。

## Qt 源行为覆盖清单

N/A，本任务不是 Qt 迁移，也不涉及 UI interaction 或 operation availability。

## UI 设计来源目录

N/A，本任务无 UI、图标、tooltip、文案或布局变化。

## UI / UX / 文案依据追踪

N/A，本任务无用户可见界面变化；命令行错误文案以现有脚本风格和用户诉求为依据。

## 影响模块 *(初始判断)*

- `package.json`: `postinstall` 触发 NewsNow 同步能力。
- `scripts/sync_newsnow.py`: NewsNow clone、checkout、脏改保护、overlay 应用。
- `scripts/newsnow_runtime.js`: NewsNow 状态检查和 blocker 输出。
- `engine/newsnow.lock.json`: 固定上游仓库、commit、版本和 overlay 元数据。
- `engine/newsnow-overlays/` 或等价目录: 保存 Auto-Podcast 自定义采集能力文件和 manifest。

## 验证预期

- **Test-Case Plan Review**: approved-by-ai-obvious；该任务验证点是脚本输入输出和状态断言。
- **Quality Vision**: N/A，无 UI/UX 变化。
- **Acceptance Rubric**: `acceptance-rubric.md` 可在 plan 阶段生成或标记 N/A；至少要覆盖 clone、lock、overlay、错误处理。
- **Build**: `npm run check:newsnow`、`npm run sync:newsnow`、`npm install` postinstall smoke。
- **Automated Tests**: 如存在脚本测试框架则补充；否则用命令级 smoke 和状态 JSON 验证。
- **Runtime/UI Smoke**: N/A，无 UI 路径。
- **Device Validation**: N/A。
- **Downstream Check**: `scripts/newsnow_runtime.js status` 能识别 overlay 状态；必要时 `npm run setup:newsnow` 作为依赖安装验证。
- **AI Self-Acceptance**: PASS 前必须记录命令输出、锁定 commit、本地 `package.json` 存在、overlay manifest 状态。

## 非目标

- 不提交 `engine/newsnow/` 上游源码目录。
- 不升级 NewsNow 到新版本，除非另有明确锁定变更。
- 不重写 TrendRadar 采集逻辑。
- 不改发现页 UI 或 Electron IPC。
- 不静默覆盖用户在 `engine/newsnow` 中的未提交改动。

## 假设

- `engine/newsnow.lock.json` 中的 `commit` 是当前应部署的固定版本。
- 用户希望自定义采集能力由 Auto-Podcast 仓库维护，且每次同步后可重复应用。
- 本机允许 `npm install` 访问 GitHub；网络失败应作为明确 blocker，而不是假成功。

## 待确认问题

- N/A；固定版本和能力边界已由用户诉求及现有 lock 文件给出。
