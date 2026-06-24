# 改进候选清单

## 候选 1

- 类型: Evidence / workflow execution
- 经验: UI 配置类 bug 在进入人工验收前，应至少完成一次目标入口到目标弹窗的 targeted browser/CDP smoke，并记录 warning 可见性、按钮状态和关键状态页。
- 触发条件: 用户反馈“全局已配置，但局部 UI 仍提示未配置”或类似配置传播 bug。
- 推荐落盘位置: 暂保留在本 feature；若重复发生，可增强 `speckit-ai-self-acceptance` 或新增 targeted smoke helper。
- 预期收益: 减少只验证配置存储、不验证 UI 传参链路的漏检。
- 过度泛化风险: 不应要求所有 UI 文案小改都跑完整 Electron CDP；只适用于配置传播、入口门禁、状态转换类 bug。
- 高级模型上下文收益: 明确最小证据包，避免广泛扫描代码或依赖人工描述判断。
- 可脚本化程度: 中；DOM 文案、按钮 disabled、mock IPC 调用次数可脚本化，真实模型质量不可脚本化。
- 最小决策证据包: feature plan、入口组件 diff、targeted smoke 截图、`llmCallCount`、page errors。
- 分类: Evidence / Tests or automation scripts
- 人工审核结论: pending
- 审核人/来源: user correction and current retrospective
- 批准范围: N/A

## 候选 2

- 类型: Branch / commit readiness
- 经验: commit 前应显式比较 `.specify/feature.json.spec_branch` 与当前 `git branch --show-current`，并在 workflow state 或 commit preflight 中暴露 mismatch。
- 触发条件: Spec Kit feature branch metadata 存在，但当前实际分支不是该分支。
- 推荐落盘位置: commit preflight / `validate-feature-artifacts` 扩展候选。
- 预期收益: 避免在 `main` 上完成本地 feature commit，或在 dirty worktree 中混入其它 feature。
- 过度泛化风险: 有些仓库策略允许在 base branch 上直接修复；脚本应读 workspace branch policy，不应硬性失败所有 mismatch。
- 高级模型上下文收益: 把分支一致性变为机械事实，减少 LLM 临场判断。
- 可脚本化程度: 高。
- 最小决策证据包: `.specify/feature.json`, `.specify/workspace.yml`, `git branch --show-current`, `git status --short`.
- 分类: Tests or automation scripts
- 人工审核结论: pending
- 审核人/来源: current retrospective
- 批准范围: N/A
