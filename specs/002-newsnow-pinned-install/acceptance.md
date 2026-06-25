# Acceptance: NewsNow 固定版本安装与自定义采集能力部署

## Status

- AI Self-Acceptance: PASS
- Human Acceptance: PASS
- Human confirmation: 用户在 2026-06-25 明确反馈“人工验收通过”。
- Remaining blockers: N/A

## Scope Accepted

- `npm install` 会执行 NewsNow 固定版本同步和 runtime setup。
- 默认 NewsNow 版本锁定为 `0.0.40`，commit 为 `290f1a67da745d77e4ed23eb096f6ad7d8f0322e`。
- Auto-Podcast 自定义数据源以仓库内 overlay 的形式维护，安装/同步后应用到 `engine/newsnow/`。
- `npm run check:newsnow` 能报告 clone、commit、依赖、构建和 overlay 状态。
- `engine/newsnow/` 作为外部 clone 继续不入库。

## Accepted Validation Evidence

| Command | Result | Evidence |
|---------|--------|----------|
| `npm install` | PASS | postinstall 执行 `sync_newsnow.py` 和 `newsnow_runtime.js setup`，状态为 `success:true`。 |
| `npm run sync:newsnow` | PASS | 本地 checkout 已位于 lock commit，overlay 已应用。 |
| `npm run check:newsnow` | PASS | `success:true`、`overlayApplied:true`、`overlayErrors:[]`、`blocker:""`。 |
| `npm run verify` | PASS | 配置、节点、TrendRadar settings 验证通过。 |
| `npm run build:newsnow` | PASS | NewsNow server build 成功，状态为 `built:true`。 |
| `npm run build` | PASS | TypeScript 与 Vite production build 通过。 |

## Accepted Non-Blocking Warnings

- Node `v23.9.0` 触发 `eslint-visitor-keys@5.0.1` 的 `EBADENGINE` warning，安装退出码为 0。
- 本机额外证书路径 `D:\UserData\Desktop\tp-link-CA.crt` 缺失导致 warning，不影响安装或构建。
- `npm run build:newsnow` 中上游 favicon 下载 `autopodcast` 图标出现一次 `ECONNRESET` 日志，但命令退出码为 0。

## Decision

本 feature 已满足当前规格、验收准则和人工验收要求，可进入 retrospective 与 commit 阶段。
