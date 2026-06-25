# Implementation Plan: NewsNow 固定版本安装与自定义采集能力部署

**Branch**: `002-newsnow-pinned-install` | **Date**: 2026-06-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-newsnow-pinned-install/spec.md`

## L2 Artifact Contract

Required sections for L2 are: `人类审核摘要`, `概览`, `分流对齐`,
`AI Context Contract`, `Root Cause Evidence`, `技术上下文`, `影响模块与边界`,
`Quality Vision Link`, `测试用例计划`, `Acceptance Rubric Link`,
`Implementation Slices`, `验证计划`, and `AI Self-Acceptance Contract`.

Keep this plan as a decision map. Put detailed runtime facts in `fact-pack.md`,
raw command evidence in `evidence.md`, and durable facts in code or selected
knowledge/gate maps.

## 人类审核摘要

- 目标: `npm install` 自动同步本地 NewsNow 到锁定 commit，并应用 Auto-Podcast 自定义采集 overlay。
- 实际范围: `scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`engine/newsnow.lock.json`、新增 `engine/newsnow-overlays/`。
- 主要风险: 网络失败、半初始化 git 目录、overlay 与上游文件冲突、重复同步造成脏状态误判。
- 验证入口: `npm run sync:newsnow`、`npm run check:newsnow`、`npm install --ignore-scripts` 后手动运行 postinstall 等价链路。
- 下一阶段: `speckit-analyze` 可自动通过，随后进入 `speckit-implement`。

## 必需人工决策

- N/A

## 概览

沿用现有外部引擎模式，保持 `engine/newsnow/` 为忽略的 clone 目录。同步脚本负责 checkout `engine/newsnow.lock.json` 的固定 commit，并在每次同步后应用仓库内 overlay manifest。运行时状态检查读取同一 manifest，报告 clone、commit、依赖、构建和 overlay 状态。

## 分流对齐

- task_type: `new-feature`
- delivery_profile: `standard-bugfix`
- risk_level: `medium`
- risk_flags: N/A
- affected_repositories: `auto-podcast`
- selected gate packs: `select-gates` 曾因通用 repo/stage 匹配返回 `native-bridge`、`qt-parity`、`real-device`、`ui-baseline`，语义判定均为 N/A，因为本任务无 native bridge、Qt、设备或 UI 变化。
- selected knowledge guides: N/A，repository-map 和局部源码足够。

## AI Context Contract

### Required Facts

| Fact | Source or Command | Why Needed | Status |
|------|-------------------|------------|--------|
| NewsNow 固定来源 | `engine/newsnow.lock.json` | clone/checkout 的唯一版本来源 | known |
| 半初始化目录状态 | `git -C engine/newsnow rev-parse HEAD`、`package.json` 缺失 | 复现 `not cloned` 的真实状态 | known |
| NewsNow 源清单机制 | `server/sources/*`、`shared/pre-sources.ts`、`server/glob.d.ts`、`scripts/source.ts` | 选择 overlay 目标 | known |
| 运行时状态入口 | `scripts/newsnow_runtime.js status` | 新增 overlay blocker | known |

### Context To Load

| Context | Trigger | Reason |
|---------|---------|--------|
| `scripts/sync_newsnow.py` | 实现同步/overlay | 主写入点 |
| `scripts/newsnow_runtime.js` | 实现状态检查 | 主写入点 |
| `engine/newsnow.lock.json` | 固定版本和 overlay 元数据 | 主写入点 |
| `engine/newsnow` 局部源码 | 设计 overlay 文件 | 只读取锁定提交结构 |

### Context To Avoid

| Context | Reason |
|---------|--------|
| 全量 `engine/trendradar` 源码 | 本任务不改 TrendRadar |
| `src/` UI 文件 | 本任务无 UI 变化 |
| 旧 `specs/*` | 与当前外部引擎安装能力无关 |

### Missing Context / Blockers

- N/A

## Root Cause Evidence

N/A，本任务为安装/工具链能力扩展，不是 bugfix。已知症状是 `engine/newsnow` 可处于半初始化或缺失状态，规格已将其作为场景处理。

## 技术上下文

- Existing pattern/API/helper to reuse: `engine/trendradar.lock.json` 的外部引擎锁定模式、现有 `scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`package.json postinstall`。
- Source behavior or design source: NewsNow 固定提交 `290f1a67da745d77e4ed23eb096f6ad7d8f0322e` 使用 `server/sources/*` getter 和 `shared/pre-sources.ts` metadata。
- Build/package/runtime facts: `pnpm install --frozen-lockfile` 安装 NewsNow 依赖；`pnpm run build` 构建；`npm run check:newsnow` 做状态检查。
- External constraints: GitHub 网络可用性、Node `>=20`、pnpm 可用性。

## 影响模块与边界

| Repository | Files / Areas | Responsibility | Write Scope | Forbidden Scope |
|------------|---------------|----------------|-------------|-----------------|
| `auto-podcast` | `scripts/sync_newsnow.py` | clone、checkout、overlay 应用、错误输出 | 可改 | 不引入 UI/Electron 协议变化 |
| `auto-podcast` | `scripts/newsnow_runtime.js` | NewsNow 状态和 blocker | 可改 | 不启动服务、不安装依赖 |
| `auto-podcast` | `engine/newsnow.lock.json` | 固定版本和 overlay manifest 引用 | 可改 | 不指向 floating latest |
| `auto-podcast` | `engine/newsnow-overlays/` | Auto-Podcast 自定义采集能力源码 | 可新增 | 不提交 `engine/newsnow/` 上游 clone |
| `auto-podcast` | `package.json` | postinstall 脚本链路 | 仅必要时微调 | 不重构全部 scripts |

## UI 展示、Biz 转发与 Libs 事实边界

N/A，本任务不涉及 UI/Biz/Libs 运行时事实。

## Identity / State / API Boundary

N/A，本任务不涉及身份、状态、bridge、RPC/N-API、JS/UI 或 public API。

## Gate Pack Plan

| Gate | Why Selected | Required Evidence | Missing Facts |
|------|--------------|-------------------|---------------|
| N/A | `select-gates` 的 native/Qt/device/UI 匹配与本任务语义不符 | 命令级 smoke 即可 | N/A |

## Source Behavior Execution Map

N/A，本任务不是 Qt-to-frontend 迁移。

## UI / UX / 文案 Evidence Gate

N/A，本任务无可见 UI/UX/copy/style 变化。

## Quality Vision Link

- `quality-vision.md`: N/A
- Quality tier: N/A
- UI baseline status: N/A

## 宪章检查

- 最小范围变更: 只改 NewsNow 安装/状态检查和 overlay。
- 既有模式优先: 复用现有 lock、sync、runtime status、postinstall 结构。
- 兼容边界: 不提交外部 clone；不改变 TrendRadar/Electron IPC 协议。

## 测试用例计划

| ID | Type | Scenario/Requirement | Test Intent | Target Path/Command | Fixture/Data | Review Status |
|----|------|----------------------|-------------|---------------------|--------------|---------------|
| TP-001 | api-test | CS1 / FR-001..FR-003 | 验证同步到锁定 commit，半初始化目录可恢复 | `npm run sync:newsnow`、`git -C engine/newsnow rev-parse HEAD` | 现有 `engine/newsnow.lock.json` | approved-by-ai-obvious |
| TP-002 | api-test | CS2 / FR-004..FR-005 | 验证 overlay 文件和 patch 已应用 | `npm run sync:newsnow`、检查 overlay state/status JSON | `engine/newsnow-overlays/auto-podcast` | approved-by-ai-obvious |
| TP-003 | smoke | CS3 / FR-006..FR-007 | 验证状态检查报告 overlay、commit、依赖 blocker | `npm run check:newsnow` | 当前本机 Node/pnpm/NewsNow 工作树 | approved-by-ai-obvious |
| TP-004 | E2E | N/A | 本仓库当前 E2E unsupported，且本任务无 UI | N/A | N/A | approved-by-ai-obvious |

## Acceptance Rubric Link

- `acceptance-rubric.md`: [acceptance-rubric.md](acceptance-rubric.md)
- Essential gate count: 4
- Pitfall count: 3

## Implementation Slices

| Slice | Goal | Allowed Write Scope | Forbidden Scope | Validation | Stop Condition |
|-------|------|---------------------|-----------------|------------|----------------|
| 1 | 同步脚本支持固定 clone、半初始化恢复、overlay 应用 | `scripts/sync_newsnow.py`、`engine/newsnow.lock.json`、`engine/newsnow-overlays/` | `engine/newsnow/` 入库、TrendRadar 改造 | `npm run sync:newsnow`、HEAD/overlay 检查 | git fetch 无法访问且无本地缓存 |
| 2 | 状态检查暴露 overlay 和 blocker | `scripts/newsnow_runtime.js` | Electron IPC/UI 语义变化 | `npm run check:newsnow` | 状态 JSON 无法表达失败原因 |

## Supporting Artifacts

- `acceptance-rubric.md`
- `evidence.md` 在实现验证后生成。
- `research.md`: N/A，锁定提交和源码结构已由局部读取确认。
- `data-model.md`: N/A，无持久业务数据模型。
- `contracts/`: N/A，不新增 public API；脚本 IO 在 plan 中记录。
- `quickstart.md`: N/A，验证命令已在 plan 中足够。

## 兼容性与迁移风险

- Compatibility risk: 低到中；只影响本地安装/同步 NewsNow，不改变业务协议。
- Migration risk: 现有 `engine/newsnow/` 若有用户未提交改动，默认不覆盖。
- Rollback or containment: 回滚脚本和 overlay 目录即可；`engine/newsnow/` 可删除后重新同步。

## 验证计划

| Validation | Command / Tool | Evidence Location | AI-Owned? |
|------------|----------------|-------------------|-----------|
| Checklist | `.specify/scripts/powershell/validate-checklist.ps1 -FeatureDir specs/002-newsnow-pinned-install` | terminal output | yes |
| Sync smoke | `npm run sync:newsnow` | `evidence.md` | yes |
| Runtime status | `npm run check:newsnow` | `evidence.md` | yes |
| Build/static | `npm run verify` when implementation touches package/script contracts | `evidence.md` | yes |

## AI Self-Acceptance Contract

- Judge skill: `speckit-ai-self-acceptance`
- Rubric source: `acceptance-rubric.md`
- Required evidence: sync command output, locked/local commit equality, overlay state/status, runtime status JSON, git status.
- PASS condition: all Essential rubric rows PASS and no Pitfall triggered.
- FAIL loop target: `speckit-implement`
- BLOCKED condition: GitHub/network unavailable and no local NewsNow checkout/cached ref can verify clone behavior.

## 项目结构说明

- Existing files reused: `scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`engine/newsnow.lock.json`、`package.json`。
- New focused files: `engine/newsnow-overlays/auto-podcast/*`。
- Generated/runtime artifacts excluded: `engine/newsnow/`、`engine/newsnow/node_modules/`、`engine/newsnow/dist/`。

## 复杂度跟踪

- N/A
