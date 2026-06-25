# Rubric Score: NewsNow 固定版本安装与自定义采集能力部署

## Hard Gate Conclusion

- Hard gate PASS。
- AI Self-Acceptance: PASS。
- Human Acceptance: PASS。
- Retrospective status: completed。
- Commit message validation: PASS。
- Post-commit self-check: PASS。
- API validation plan: present。
- E2E validation: N/A with reason，本任务无 UI/runtime page surface。
- Plugin/package gate: N/A。

## Score Table

| Dimension | Score | Weight | Evidence | 扣分 |
|-----------|------:|-------:|----------|------|
| L1 功能与需求闭合 | 100 | 0.30 | `spec.md`、`acceptance.md`、`validation.md`；用户确认人工验收通过。 | 无 |
| L2 验证与证据 | 94 | 0.25 | `evidence.md` 记录 install、sync、check、verify、build:newsnow、build 全部通过。 | 未启动 NewsNow API 服务做真实 RSS 请求；该 accepted gap 已记录。 |
| L3 工作流阶段合规 | 100 | 0.25 | `workflow-state.json`、`workflow-record.md`、post-commit self-check 通过。 | 无 |
| L4 交付与仓库状态 | 96 | 0.10 | 最终 amend 提交已生成；提交信息二次校验通过；未提交 `engine/newsnow/`。 | rubric 文件为 post-commit 终态证据，需 amend 一次纳入当前提交。 |
| L5 上下文与自动化治理 | 96 | 0.10 | 使用默认上下文、当前 feature artifacts 和 Spec Kit validators；未加载无关旧 feature。 | PowerShell profile 干扰初始读文件，已改用 `login:false` 消除。 |

## Overall

- Overall Weighted Score: 97.70
- weighted_total: 97.70
- AI acceptance decision: PASS
- Human acceptance readiness: PASS
- complete-branch: allowed after this rubric validates, but not executed unless requested.

## Evidence Paths

- `specs/002-newsnow-pinned-install/evidence.md`
- `specs/002-newsnow-pinned-install/validation.md`
- `specs/002-newsnow-pinned-install/acceptance.md`
- `specs/002-newsnow-pinned-install/workflow-record.md`
- `specs/002-newsnow-pinned-install/improvement-candidates.md`
- `specs/002-newsnow-pinned-install/workflow-state.json`

## Deduction Reasons

- L2 扣 6 分：未启动 NewsNow API 服务做真实 RSS 请求。该项是 accepted gap，因为本 feature 的目标是安装、固定版本、overlay 部署和状态检查。
- L4 扣 4 分：Rubric 属于 post-commit 终态证据，需要一次 amend 纳入提交。
- L5 扣 4 分：首次 PowerShell 读取受用户 profile 干扰超时，后续使用 `login:false` 固化规避方式。
