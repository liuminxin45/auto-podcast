# Tasks: NewsNow 固定版本安装与自定义采集能力部署

## L3 Artifact Contract

- **Layer**: L3 Implementation Tasks
- **Purpose**: map approved plan slices to ordered source edits and validation.
- **Source**: `spec.md`, `plan.md`, `acceptance-rubric.md`
- **Scope rule**: tasks must not add behavior outside `Implementation Slices`.

## 人类审核摘要

- **结论**: 两个实现切片足够覆盖需求。
- **阻塞项**: N/A。
- **最高风险**: overlay 修改上游 tracked 文件后，后续同步不能误判为未知脏改。
- **验证缺口**: N/A，使用命令级 smoke。
- **建议下一步**: `speckit-implement`。

## Implementation Slices

### Slice 1 - 同步脚本和 overlay

- [x] T001 在 `engine/newsnow.lock.json` 记录 overlay manifest。
- [x] T002 新增 `engine/newsnow-overlays/auto-podcast/manifest.json`。
- [x] T003 新增 `engine/newsnow-overlays/auto-podcast/server/sources/autopodcast.ts`。
- [x] T004 修改 `scripts/sync_newsnow.py`，支持缺失/半初始化 clone、固定 checkout、overlay file copy 和 text patch。
- [x] T005 修改 `scripts/sync_newsnow.py`，写入 `.auto-podcast-overlay.json` 状态并避免默认静默覆盖未知 dirty tree。

### Slice 2 - 状态检查和验证

- [x] T006 修改 `scripts/newsnow_runtime.js`，读取 overlay manifest 并报告 `overlayApplied`、`overlayErrors`。
- [x] T007 运行 `npm run sync:newsnow`，确认本地 HEAD 等于 lock commit。
- [x] T008 运行 `npm run check:newsnow`，确认 overlay 状态进入 JSON。
- [x] T009 运行 `npm run verify` 或记录明确 blocker。

## Write Scope

- `scripts/sync_newsnow.py`
- `scripts/newsnow_runtime.js`
- `engine/newsnow.lock.json`
- `engine/newsnow-overlays/auto-podcast/`
- `specs/002-newsnow-pinned-install/`

## Forbidden Scope

- 不提交 `engine/newsnow/`。
- 不改发现页 UI。
- 不改 Electron IPC。
- 不改 TrendRadar Python bridge。

## Stop Conditions

- GitHub 网络完全不可达且本地无可用 NewsNow checkout。
- overlay 与上游文件冲突且无法通过幂等 patch 表达。
- `npm run check:newsnow` 无法提供明确 blocker。
