# 发现页状态隔离与采集修复计划

## L2 Artifact Contract

- Layer: L2 Technical Plan
- Purpose: map the accepted L1 behavior to source boundaries, root-cause evidence,
  validation commands, implementation slices, and AI self-acceptance criteria.
- Source spec: `spec.md`
- Workflow state: `workflow-state.json`
- Delivery profile: `standard-bugfix`
- Risk level: `medium`

## 人类审核摘要

- 一句话结论: 修复发现页状态隔离、采集 loading、LLM 配置引导、图标语义和日志噪声，并补充自动选题全局 LLM 配置传播修复。
- 写入范围: React/Vite 前端源文件和 feature-local Spec Kit artifact。
- 不写入范围: TrendRadar 外部源、真实外部 LLM 服务、公共 API、NativePlugin、设备运行态。
- 验收证据: `validation.md`、`acceptance.md`、`acceptance-checklist.md`、`cdp-screenshots/screenshots-index.md`。

## Root Cause Evidence

- Symptom: 新节目发现页继承旧素材；采集按钮可能卡 loading；全局 LLM 已配置时自动选题仍提示未配置；自动选题 mock LLM 返回后未进入定稿页。
- Call Path: `DiscoverPanel` -> `AutoTopicModal` -> `useAutoTopic` -> `llmService` / Electron LLM IPC。
- Evidence: `DiscoverPanel` 原先向 `AutoTopicModal` 传入 `llmConfig={null}`；browser smoke 修复前显示 LLM 已调用但 UI 停在 running 结束态。
- Excluded Alternatives: 真实外部模型服务不可用不是本次根因；mock LLM 已证明 app-side 调用与 JSON 解析链路可工作。
- Counterexample: 注入全局 search/text LLM 配置后，修复后弹窗不再显示未配置，开始按钮可用，mock LLM 调用后进入定稿页。
- Blast Radius: 发现页、自动选题弹窗、自动选题 hook；不改变后端节点协议。
- Validation Mapping: LLM 配置传播由 browser smoke 覆盖；hook 配置 guard 由 Vitest 覆盖；构建由 `npm run build` 覆盖。
- Confidence: high for app-side fix, medium for real external model output quality because it remains provider-dependent。

## 技术上下文

- Frontend: React, TypeScript, Vite, Ant Design。
- State source: 当前节目 workflow state 与发现页本地 state。
- LLM config source: `llmConfigResolver.getLLMConfig('discover')`，优先发现/搜索模型，回退文本模型。
- Runtime validation: Vite/browser targeted smoke and Electron CDP acceptance script。

## AI Context Contract

- 必读: `.specify/workspace.yml`、`.specify/memory/repository-map.md`、`.specify/feature.json`、`ai/workflows/task-routing.md`、本 `plan.md`。
- 需要时读取: `src/components/DiscoverPanel.tsx`、`src/components/AutoTopicModal.tsx`、`src/hooks/useAutoTopic.ts`、`validation.md`。
- 避免默认读取: old completed `specs/*`、broad `ai/knowledge/*`、generated build output。
- 决策关键事实: 自动选题 modal 必须拿到全局 LLM 配置，running 完成态必须进入 review。

## 影响模块与边界

- `src/components/DiscoverPanel.tsx`: 发现页状态、采集动作、自动选题入口、LLM 配置传入。
- `src/components/AutoTopicModal.tsx`: LLM 配置 guard、开始按钮、处理完成后的定稿页切换。
- `src/hooks/useAutoTopic.ts`: 自动选题执行、缺配置提示、LLM 调用和结果解析。
- `src/App.tsx`: 主流程返回图标。
- Boundary: 不新增外部数据源，不修改 Python 节点协议，不验证真实外部 LLM 稳定性。

## Quality Vision Link

- Quality source: `quality-vision.md`
- UI baseline: 用户明确指出图标、提示、loading 和状态污染问题；本次按现有 Ant Design/工作台样式修复，不做整体视觉重设计。

## 测试用例计划

Review status: approved-by-ai-obvious

| Area | Type | Plan | Status |
| --- | --- | --- | --- |
| Config/schema | API/interface | `npm run verify` 覆盖配置、节点结构和 TrendRadar discovery settings | required |
| Hook behavior | API/interface | `npx vitest run src/hooks/__tests__/useAutoTopic.test.tsx --reporter=dot` 覆盖缺 LLM 配置、执行、错误和日志 | required |
| Frontend build | Build | `npx tsc --noEmit --pretty false` and `npm run build` | required |
| UI flow | E2E/interface flow | browser targeted smoke 覆盖自动选题 LLM 配置、开始按钮和定稿页状态 | required |
| Full Electron CDP | E2E/interface flow | `npm run acceptance:cdp`; known accepted gap: unrelated `rank_threshold` assertion may fail | accepted gap |
| Real external LLM | E2E | N/A with reason: provider quality and JSON output stability are outside this app-side bugfix | N/A |

## Validation Plan

This section mirrors `验证计划` for deterministic validation tooling.

## Acceptance Rubric Link

- Rubric: `acceptance-rubric.md`
- AI self-acceptance result: `validation.md`
- Human acceptance: `acceptance.md` and `acceptance-checklist.md`

## Implementation Slices

1. 发现页状态隔离和采集 loading 闭环。
2. LLM 依赖入口 guard、设置引导和自动选题全局 LLM 配置传播。
3. 自动选题执行完成后进入定稿页。
4. 返回图标、设置图标和 console 刷屏修复。
5. 验证、acceptance、retrospective 和 commit gate artifact closure。

## 验证计划

- `npm run verify`
- `npx tsc --noEmit --pretty false`
- `npx vitest run src/hooks/__tests__/useAutoTopic.test.tsx --reporter=dot`
- `npm run build`
- `git diff --check`
- `npm run acceptance:cdp`
- browser targeted smoke for automatic topic LLM config and execution review transition

## AI Self-Acceptance Contract

- Required status: PASS before human acceptance and commit.
- Required evidence: validation matrix, result interpretation, evidence links, accepted gaps, browser/CDP screenshot references.
- Current artifact: `validation.md`

## 问题范围

本次处理发现页已暴露的运行问题，不改变工作流协议和后端节点语义。

## 根因判断

- 新节目显示旧新闻：发现页当前优先读取全局 `radarState.contents`，而不是当前 workflow 的 `state.fetch_contents`，导致跨节目缓存串入。
- “立即采集”长时间转圈：前端等待 `radarRunOnce` 无超时兜底，且采集结果没有写回当前节目状态。
- “返回”按钮使用 X：多个主流程页的返回按钮仍复用 `CloseOutlined`。
- “智能标签”无 LLM 也可开启：开关切换时没有先校验 `loadLLMConfig()` 是否返回有效配置。
- 清空新闻后控制台刷屏：`filteredSignals` 计算中残留高频 `console.log`。
- 雷达设置图标语义不准：设置入口仍用雷达图标。

## 实施步骤

1. 发现页只读取当前节目 `fetch_contents`，即时采集成功后将内容写入当前 workflow state。
2. 采集按钮增加前端超时兜底和明确错误提示，失败后恢复 loading。
3. 智能标签开启前校验 LLM 配置；未配置时保持关闭并提示到设置页配置。
4. 清空新闻时同步清空当前 workflow 的发现候选、入箱状态、已选素材和原始内容。
5. 移除发现页高频调试日志。
6. 主流程页顶部返回按钮统一改为返回箭头；保留删除、关闭、弹窗关闭等 X 图标。
7. 雷达设置按钮改用设置图标。

## 验证计划

- `npm run verify`
- `npm run build`
- 静态扫描确认发现页不再输出 `fetchContents:` 调试日志。
- 如本地应用可启动，进行 CDP/浏览器自测：新建节目、进入发现、清空新闻、立即采集、智能标签未配置提示、返回按钮图标。

