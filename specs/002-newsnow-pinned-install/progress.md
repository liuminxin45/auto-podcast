# Progress: NewsNow 固定版本安装与自定义采集能力部署

## 2026-06-25

- 创建 Spec Kit 分支 `002-newsnow-pinned-install`。
- 明确范围：`npm install` 自动同步 `engine/newsnow` 到锁定 commit，并应用 Auto-Podcast 自定义采集 overlay。
- 新增 `engine/newsnow-overlays/auto-podcast`：
  - `server/sources/autopodcast.ts`：从 `AUTO_PODCAST_NEWSNOW_FEEDS` 读取 RSS feed 列表并转换为 NewsNow `NewsItem`。
  - `manifest.json`：声明复制文件与 `pre-sources.ts`、`glob.d.ts` 补丁。
- 扩展 `scripts/sync_newsnow.py`：
  - 从 `engine/newsnow.lock.json` 读取 repo/ref/commit。
  - 支持半初始化 `engine/newsnow` 恢复。
  - 每次同步后应用 overlay，并写入 `.auto-podcast-overlay.json`。
  - 已锁定 commit 重入时允许 overlay/NewsNow 生成文件，阻断未知本地改动。
- 扩展 `scripts/newsnow_runtime.js`：
  - 状态输出包含锁定 commit、本地 commit、依赖、构建、overlay state/errors。
  - blocker 能报告 clone 缺失、commit mismatch、overlay 未应用、依赖缺失。
- 更新 `package.json postinstall`：
  - `npm install` 现在会执行 `sync_newsnow.py` 后立即执行 `node scripts/newsnow_runtime.js setup`。
- 验证完成：
  - `npm install`: PASS。
  - `npm run sync:newsnow`: PASS。
  - `npm run check:newsnow`: PASS。
  - `npm run verify`: PASS。
  - `npm run build:newsnow`: PASS。
  - `npm run build`: PASS。
- AI Self-Acceptance: PASS。
- 人工验收: PASS，用户已确认“人工验收通过”。
- Retrospective: PASS，已记录 `workflow-record.md` 和 `improvement-candidates.md`。

## 已接受的非阻断警告

- `npm install` 中 Node v23.9.0 触发 `eslint-visitor-keys` 的 `EBADENGINE` warning，但安装退出码为 0。
- 本机额外证书路径 `D:\UserData\Desktop\tp-link-CA.crt` 缺失导致 npm/Node 输出 warning，但不影响安装或构建。
- `npm run build:newsnow` 中上游 favicon 下载对 `autopodcast` 输出一次 `ECONNRESET` error 日志；该脚本吞掉错误，构建退出码为 0，NewsNow server build 成功。
