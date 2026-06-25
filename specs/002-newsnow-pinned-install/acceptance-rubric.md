# 验收评分准则: NewsNow 固定版本安装与自定义采集能力部署

## 评分规则

- Hard gates: every `Essential` must be `PASS`; every relevant `Pitfall` must be `PASS` as "not triggered".
- 加权分只作参考，不能覆盖硬门禁失败。
- 状态值固定为：`PASS | FAIL | BLOCKED | N/A`。
- 最终 Rubric 评分只在一轮 post-commit self-check 之后输出；plan / implement / acceptance 阶段只维护准则定义、证据入口和 hard gates。

## 评分项

| ID | 层级 | 重要性 | 权重 | 准则 | 所需证据 | 通过条件 | 来源 | 状态 |
|----|-------|------------|--------|-----------|-------------------|----------------|--------|--------|
| R-001 | L1 功能与需求闭合 | Essential | 1.0 | 同步流程以 `engine/newsnow.lock.json` 的固定 commit 为唯一默认来源 | `npm run sync:newsnow` 输出、`git -C engine/newsnow rev-parse HEAD` | 本地 HEAD 等于 lock commit | FR-001..FR-003 | PASS |
| R-002 | L1 功能与需求闭合 | Essential | 1.0 | 半初始化或缺失 `engine/newsnow` 能恢复为完整源码工作树 | 清理/半初始化后的同步证据或当前目录恢复证据 | `engine/newsnow/package.json` 存在且 git HEAD 有效 | CS1 | PASS |
| R-003 | L1 功能与需求闭合 | Essential | 1.0 | Auto-Podcast 自定义采集 overlay 被仓库内 manifest 管理并应用到 NewsNow | overlay manifest、目标文件、状态 JSON | overlay 文件和 patch 均存在于目标工作树 | CS2 / FR-004..FR-005 | PASS |
| R-004 | L2 验证与证据 | Essential | 1.0 | `npm run check:newsnow` 能报告 clone、commit、依赖、构建和 overlay 状态 | status JSON 或命令输出 | blocker 精确，overlay 状态可读 | CS3 / FR-006..FR-007 | PASS |
| R-005 | L3 工作流阶段合规 | Important | 0.7 | Spec、plan、checklist、rubric 和 evidence 保持一致 | artifact paths、workflow-state | 无阶段 artifact 缺失 | Spec Kit workflow | PASS |
| R-006 | L4 交付与仓库状态 | Important | 0.7 | 未提交 `engine/newsnow/` 外部 clone 和生成物 | `git status --short` | 只有源码、overlay、spec artifact 进入 diff | 非目标 | PASS |
| P-001 | Pitfall | Pitfall | 0.9 | 同步脚本不允许静默覆盖用户在 NewsNow 工作树中的未知改动 | 脏改场景逻辑或代码检查 | 未触发 | FR-007 | PASS |
| P-002 | Pitfall | Pitfall | 0.9 | `npm install` 不应只创建空 `.git` 半初始化目录后假成功 | sync/status 证据 | 未触发 | CS1 | PASS |
| P-003 | Pitfall | Pitfall | 0.9 | 自定义采集能力不应只存在于 `.gitignore` 的 `engine/newsnow/` | git diff 和 overlay manifest | 未触发 | FR-005 | PASS |

## 评审摘要

- Essential 是否全部通过: 是。
- Pitfall 是否均未触发: 是。
- 加权分: 待 post-commit self-check 后填写。
- 阻塞项: N/A。
- 下一步: `speckit-acceptance`。

## 实际流程评分审计（Actual Workflow Rubric Audit）

> Only fill after `speckit-post-commit-self-check` completes.

| 维度 | 权重 | 评分 0-100 | 证据 | 主要风险 / Pitfall |
|-----------|--------|-------------|----------|---------------------|
| L1 功能与需求闭合 | 0.30 | 100 | `spec.md`、`acceptance.md`、用户人工验收确认 | 无 |
| L2 验证与证据 | 0.25 | 94 | `evidence.md` | accepted gap: 未启动 NewsNow API 服务做真实 RSS 请求。 |
| L3 工作流阶段合规 | 0.25 | 100 | `workflow-state.json`、`workflow-record.md` | 无 |
| L4 交付与仓库状态 | 0.10 | 96 | 最终 amend 提交、提交信息校验 | rubric 终态证据需 amend 一次纳入提交。 |
| L5 上下文与自动化治理 | 0.10 | 96 | 默认上下文、validators、当前 feature artifacts | PowerShell profile 干扰已规避。 |
| Hard gates | hard gate | PASS | `validation.md`、post-commit self-check、提交信息校验 | AI Self-Acceptance, retrospective, API/E2E, commit message, self-check |

- Overall Weighted Score / 总加权分: 97.70
- AI acceptance decision / AI 验收结论: PASS
- Human acceptance readiness / 人工验收准备状态: PASS
- Complete-branch allowed / 是否允许 complete-branch: allowed, 本阶段不执行
- 扣分原因: 真实 RSS 服务请求未在本 feature 范围内执行；rubric 终态证据需 amend；PowerShell profile 初始干扰已规避。
- Accepted gap 证据: `validation.md`、`rubric-score.md`
