# Workflow Record: NewsNow 固定版本安装与自定义采集能力部署

## Route

- Task type: `new-feature`
- Risk level: `medium`
- Delivery profile: `standard-bugfix`
- Feature branch: `002-newsnow-pinned-install`
- Affected repository: `auto-podcast`

## Stage Record

| Stage | Status | Evidence |
|-------|--------|----------|
| specify | PASS | `spec.md`、requirements checklist 已生成。 |
| plan | PASS | `plan.md` 定义两段实现切片，未扩大到 UI/Electron IPC。 |
| tasks | PASS | `tasks.md` 覆盖同步脚本、overlay、状态检查和验证。 |
| implement | PASS | 源码变更完成，任务项全部关闭。 |
| validation | PASS | `npm install`、`sync:newsnow`、`check:newsnow`、`verify`、`build:newsnow`、`build` 均通过。 |
| ai-self-acceptance | PASS | `validation.md` 记录全部 rubric 行通过。 |
| acceptance | PASS | 用户确认人工验收通过。 |
| retrospective | PASS | 本文件与 `improvement-candidates.md` 已记录。 |

## Engineering Decisions

- 保持 `engine/newsnow/` 为忽略的外部 clone，不提交上游源码。
- 将 Auto-Podcast 自定义采集能力放在入库 overlay 中，安装/同步时复制和 patch 到 NewsNow 工作树。
- 允许 NewsNow 生成文件和 overlay patch 目标在外部 clone 中产生 dirty diff，但同步脚本阻断未知本地改动。
- `postinstall` 中先同步 NewsNow，再运行 `newsnow_runtime.js setup`，确保 `npm install` 后能立即检查状态。

## Validation Boundary

- 本 feature 验证安装、版本锁定、overlay 应用、状态检查和构建。
- 未启动 NewsNow API 服务做真实 RSS 端到端请求；该行为属于后续发现页/运行时集成验证。

## Outcome

当前 feature 可提交。分支按 workspace 配置为 local-only，不在本阶段推送远端。
