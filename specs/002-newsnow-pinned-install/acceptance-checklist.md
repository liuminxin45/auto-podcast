# Acceptance Checklist: NewsNow 固定版本安装与自定义采集能力部署

- [x] 固定 NewsNow 版本与 commit 已写入 `engine/newsnow.lock.json`。
- [x] `npm install` 会自动同步 NewsNow 并执行 runtime setup。
- [x] 缺失或半初始化的 `engine/newsnow` 可由同步脚本恢复。
- [x] 自定义采集能力在 `engine/newsnow-overlays/auto-podcast` 中入库维护。
- [x] overlay 应用后能被 `npm run check:newsnow` 识别。
- [x] 状态检查能报告 clone、commit、依赖、构建、overlay blocker。
- [x] 未提交 `engine/newsnow/` 外部 clone 或构建产物。
- [x] `npm run sync:newsnow` 通过。
- [x] `npm run check:newsnow` 通过。
- [x] `npm run verify` 通过。
- [x] `npm run build:newsnow` 通过。
- [x] `npm run build` 通过。
- [x] AI Self-Acceptance 通过。
- [x] 人工验收通过。
