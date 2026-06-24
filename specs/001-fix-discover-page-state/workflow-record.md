# 工作流留痕: 001-fix-discover-page-state

## 1. 基本信息

- Feature: `001-fix-discover-page-state`
- Branch: 期望 `001-fix-discover-page-state`；提交前实际分支切换为 `codex/fix-autotopic-llm-config`
- Repositories: `auto-podcast`
- Delivery profile: `standard-bugfix`
- Risk level: `medium`
- Final acceptance: 用户于 2026-06-24 回复“人工验收通过，继续往下执行”

## 2. 关键用户输入

- 初始需求: 使用 Spec Kit 修复发现页新节目状态污染、立即采集 loading、返回图标、LLM 依赖提示、console 刷屏和雷达设置图标。
- 关键补充: 用户指出自动选题助手在已配置全局 LLM 后仍提示“未配置大模型 API”。
- 用户提供的证据: 用户说明全局设置已有 LLM，但自动选题弹窗仍要求节点设置 API Key。
- 用户纠偏: 用户要求按 Spec Kit 流程执行，并质疑未按 CDP 自验。
- 最终验收: 用户回复“人工验收通过，继续往下执行”。

## 3. AI 输出与动作链

- `speckit-specify` / `plan`: 读取 feature state、规格和计划，确认标准 bugfix。
- `speckit-implement`: 修复 `AutoTopicModal`、`DiscoverPanel`、`useAutoTopic` 的 LLM 配置传播、配置完整性 guard 和执行完成后进入定稿页的状态转换。
- `speckit-ai-self-acceptance`: 生成 `validation.md`，判定 AI Self-Acceptance 为 PASS。
- `speckit-acceptance`: 生成 `acceptance.md`、`acceptance-checklist.md`，等待人工验收。
- `speckit-simplify`: 无产品代码清理，记录 N/A 到 `progress.md`。
- `speckit-test-hardening`: 无新增测试文件，记录 N/A 到 `progress.md`。
- `speckit-retrospective`: 生成本文件和 `improvement-candidates.md`。
- 修改文件:
  - `src/components/DiscoverPanel.tsx`
  - `src/components/AutoTopicModal.tsx`
  - `src/hooks/useAutoTopic.ts`
  - `specs/001-fix-discover-page-state/*`
- 验证命令:
  - `npm run verify`: PASS
  - `npx tsc --noEmit --pretty false`: PASS
  - `npx vitest run src/hooks/__tests__/useAutoTopic.test.tsx --reporter=dot`: PASS, 8/8
  - `npm run build`: PASS
  - `git diff --check`: PASS
  - `npm run acceptance:cdp`: PARTIAL, unrelated `rank_threshold` assertion failed
- CDP截图目录:
  - `specs/001-fix-discover-page-state/cdp-screenshots/`
  - `docs/acceptance/screenshots/2026-06-24T15-21-47-268Z/`
- 结果: 自动选题 LLM 配置读取、开始按钮启用、mock LLM 调用、定稿页展示均通过。

## 4. 错误、返工与状态变化

- 现象: 全局 LLM 已配置时，自动选题弹窗仍显示未配置。
- 错误判断或失败尝试: 初始执行没有严格按 Spec Kit/CDP 验证节奏推进，用户指出后补齐。
- 暴露问题的证据: `DiscoverPanel` 原先向 `AutoTopicModal` 传入 `llmConfig={null}`；执行级 smoke 还暴露 LLM 已返回但 UI 停在 running 结束态。
- 解决动作:
  - `DiscoverPanel` 打开自动选题前读取 `llmConfigResolver.getLLMConfig('discover')`。
  - `AutoTopicModal` 使用完整 LLM 配置 guard。
  - `AutoTopicModal` 增加完成态 effect，从 running 自动进入 review。
  - `useAutoTopic` 缺配置错误文案指向 `Settings -> AI 能力接口`。
- 最终验证: `autotopic-llm-config-enabled.png` 和 `autotopic-execution-smoke-after.png` 覆盖配置与执行路径。

## 5. 根因归类

- 信息不足: 自动选题与全局 LLM resolver 的连接点未在初始验收路径中覆盖。
- 运行时证据缺失: 早期没有先用 CDP/browser 观察真实 UI 状态，导致流程被用户纠偏。
- 源码/产物混淆: N/A。
- 计划或任务拆分不足: 原 feature 覆盖发现页多个问题，追加自动选题 bug 后需要补充专项验收。
- 工具链问题: `npm run acceptance:cdp` 存在既有 `rank_threshold` 失败，阻断全量 CDP 绿色结果。
- 多仓或分支流程问题: `.specify/feature.json` 期望分支 `001-fix-discover-page-state`；因该分支与 `main` 已分叉，提交前改用本地 `codex/fix-autotopic-llm-config` 承载后续提交。
- 其他: 当前工作树还包含前序 NewsNow 集成改动，提交范围需要谨慎。

## 6. 可复用经验

- 经验: UI 配置类 bug 不能只看 hook 或配置存储；必须验证 UI 入口是否把 resolver 结果传入具体 modal/component。
- 适用条件: 全局配置已存在但局部弹窗仍提示未配置。
- 不适用条件: 真实外部 LLM 服务不可用或模型输出格式错误，这属于服务或 prompt 稳定性问题。
- 证据: `src/components/DiscoverPanel.tsx` 原 `llmConfig={null}` 与修复后 browser smoke。

## 7. 自动化机会

- 可新增脚本: 自动选题执行级 smoke 可固化为 `acceptance:autotopic`，只验证 app-side LLM IPC mock 和 UI 状态转换。
- 可新增 checklist: acceptance checklist 增加“全局 LLM 已配时自动选题弹窗不可显示未配置”。
- 可新增 MCP/runtime evidence: 记录 browser target URL、截图和 `llmCallCount`。
- 可新增 validation/evidence 模板: `validation.md` 中区分 full CDP accepted gap 与 targeted smoke pass。
- 可新增测试: 若后续 modal 测试基础成熟，可补 `AutoTopicModal` 状态转换测试。
- 可新增 workflow gate: 对 UI 配置 bug，要求至少一次入口组件到目标弹窗的运行时 smoke。
- automation-first 判断: `llmCallCount`、warning 是否可见、review 是否可见可脚本化；是否足以代表真实模型质量仍保留 LLM/人工判断。

## 8. 现有约束审计

- 相关已有约束:
  - `AGENTS.md` 的 host CDP 验证要求。
  - `ai/workflows/task-routing.md` 的 Stage Continuation、AI Self-Acceptance、CDP/runtime evidence 要求。
  - `speckit-ai-self-acceptance`、`speckit-acceptance`、`speckit-retrospective` 技能。
- 约束状态: 规则已有，但本轮执行初期未严格落实。
- 失败归因: LLM 执行偏离，而非规则缺失。
- 优先修复位置: 先作为 `improvement-candidates.md` pending 候选；若后续重复发生，再考虑增强 acceptance preflight 或脚本化 targeted smoke。

## 9. 团队知识候选

- 候选事实: Auto-Podcast 的自动选题弹窗需要通过 `llmConfigResolver.getLLMConfig('discover')` 读取全局 search/text LLM。
- 稳定性判断: 中等；依赖当前设置服务结构。
- 来源证据: `DiscoverPanel` 修复、`AutoTopicModal` smoke、`validation.md`。
- 推荐落盘位置: 暂不推广到 `.specify/memory`；先保留在 feature retrospective。
- 审核状态: pending。

## 10. 自动化 / LLM 分工判断

- 适合规则化/脚本化: warning 可见性、开始按钮禁用状态、mock LLM 调用次数、review 页是否显示。
- 保留 LLM 判断: mock 验证是否足以替代真实外部模型调用、accepted gap 是否可接受。
- 避免自动化的原因: 真实模型输出质量和 JSON 稳定性受外部服务影响，不应作为本 bugfix 的硬 gate。

## 11. Accepted Gaps

- 已接受缺口: `npm run acceptance:cdp` 全量报告因既有 `rank_threshold` 断言失败。
- 接受依据: `validation.md` 和 `acceptance.md` 已明确说明，用户人工验收通过。
- 后续范围: 可另开 feature 修复全量 CDP 的 `rank_threshold` 断言。

## 12. 质量判断

- 任务输出质量: 通过，自动选题 LLM 配置和执行路径已修复并经人工验收。
- Spec Kit 流程质量: 中等，前半段需要用户纠偏，后续补齐 validation、acceptance、simplify、test-hardening、retrospective。
- AI 执行质量: 中等偏上，最终证据闭环完整，但初始阶段未主动按 CDP 自验。
- 剩余风险:
  - 实际提交分支为 `codex/fix-autotopic-llm-config`，与 feature branch metadata 不一致。
  - 工作树包含前序 NewsNow 集成改动，提交范围可能无法简单按文件区分。
  - 真实外部 LLM 在线质量未验证。

## 13. Rubric 审计评分准备

| 维度 | 权重 | 状态 | 证据 | 备注 |
|------|------|------|------|------|
| L1 功能正确性 | 0.40 | ready-for-post-commit-score | `validation.md`, `acceptance.md` | 人工验收已通过 |
| L2 健壮性 | 0.25 | ready-for-post-commit-score | `npm run verify`, unit tests, browser smoke | 全量 CDP 有 accepted gap |
| L3 UI 呈现 | 0.20 | ready-for-post-commit-score | screenshots index | 图标和弹窗状态覆盖 |
| L4 交互体验 | 0.15 | ready-for-post-commit-score | execution smoke | 自动进入定稿页 |
| AI 验收闭环 | hard gate | ready | `validation.md` | PASS |
| UI/UX 基线一致性 | UI gate | ready | `quality-vision.md`, screenshots | 无独立设计稿需求 |
| Spec Kit 流程执行 | process | ready-with-risk | 本文件, `progress.md` | 初期偏离已记录 |
- 总分: post-commit self-check 后填写。
- 硬门禁结论: post-commit self-check 后填写。
- 是否可交给人类验收: 已完成，用户验收通过。

## 14. 高级模型上下文效率复盘

- 决策关键事实: `llmConfig={null}`、全局 LLM resolver、自动选题执行后 UI stale state、accepted CDP gap。
- 本次过量上下文: 若只处理自动选题 LLM bug，不需要读取旧 completed specs 或 broad knowledge；实际后续未加载。
- 本次缺失结构化字段: workflow state 未记录当前实际 git branch 与 spec branch mismatch。
- 应脚本生成的证据: 自动选题 targeted smoke 的 warning/start/review/llmCallCount。
- 最小决策证据包: `feature.json`、repository-map、plan、AutoTopic/DiscoverPanel diff、targeted browser smoke、unit tests。
- 建议沉淀到 spec-kit 的位置: pending；优先在 feature-local improvement candidate 中保留。
