# Improvement Candidates: NewsNow 固定版本安装与自定义采集能力部署

## Candidate 1 - NewsNow 服务级 smoke

- Priority: Medium
- Context: 当前验收覆盖安装、同步、overlay 和构建，但未启动 NewsNow API 做真实 RSS 请求。
- Proposal: 增加一个可选 smoke：启动 NewsNow dev/server，设置 `AUTO_PODCAST_NEWSNOW_FEEDS` 指向稳定 fixture RSS，本地请求 Auto-Podcast source endpoint。
- Reason not in current scope: 本任务需求是 npm install 固定拉取和 overlay 部署，不是发现页端到端运行时验证。

## Candidate 2 - Overlay patch drift test

- Priority: Medium
- Context: overlay 依赖上游 `shared/pre-sources.ts` 和 `server/glob.d.ts` 文本结构。
- Proposal: 为 `scripts/sync_newsnow.py` 增加 fixture 级 patch drift 单元测试，提前发现上游结构变更。
- Reason not in current scope: 当前 lock commit 固定，`npm run check:newsnow` 已能报告 overlayErrors。

## Candidate 3 - Node 版本治理

- Priority: Low
- Context: 本机 Node `v23.9.0` 会触发 `eslint-visitor-keys` 的 `EBADENGINE` warning。
- Proposal: 在 README 或工程脚本中明确推荐 Node LTS 版本，并在 verify 中输出更清晰的版本建议。
- Reason not in current scope: warning 不影响当前安装、验证或构建。
