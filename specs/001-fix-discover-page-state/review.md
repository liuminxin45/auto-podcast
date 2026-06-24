# 修复发现页节目状态与交互问题 - Review

## 目标

修复发现页在节目切换、新建节目、采集、LLM 依赖能力、返回按钮、雷达设置图标和 console 日志方面的实际问题。

## 规格入口

- `spec.md`: `specs/001-fix-discover-page-state/spec.md`
- `workflow-state.json`: `specs/001-fix-discover-page-state/workflow-state.json`
- `checklists/requirements.md`: `specs/001-fix-discover-page-state/checklists/requirements.md`
- `validation.md`: `specs/001-fix-discover-page-state/validation.md`
- `acceptance.md`: `specs/001-fix-discover-page-state/acceptance.md`
- `acceptance-checklist.md`: `specs/001-fix-discover-page-state/acceptance-checklist.md`
- `progress.md`: `specs/001-fix-discover-page-state/progress.md`
- `workflow-record.md`: `specs/001-fix-discover-page-state/workflow-record.md`
- `improvement-candidates.md`: `specs/001-fix-discover-page-state/improvement-candidates.md`

## Workspace Repository Map

- **workspace_root**: `E:\Neo\auto-podcast`
- **default_base_branch**: `main`
- **repository_map**: `.specify/memory/repository-map.md`

| Repository | Path | Role | Capability / Ownership | Why affected |
|------------|------|------|-------------------------|--------------|
| `auto-podcast` | `.` | `electron-react-python-podcast-workbench` | Electron desktop shell, React/Vite authoring UI, Python podcast workflow nodes, shared state/config protocol, TrendRadar bridge, build/test scripts, docs, and runtime output conventions. | 发现页属于 React/Electron 工作台主路径。 |

## 重点审核点

1. 新节目发现页必须干净，不能继承旧节目“新闻”或选中状态。
2. “立即采集”不能永久 loading，失败也必须恢复并提示。
3. 依赖 LLM 的“智能标签”等入口在无配置时必须阻止启用并引导设置。
4. “返回”按钮图标、雷达设置图标和 console 日志噪声必须修复。

## 验证入口

- `npm run verify`
- `npm run build`
- UI/CDP smoke：新增节目、打开发现页、立即采集、清空素材、切换智能标签、检查控制台。

完整 AI 执行仍需读取 `spec.md`、后续 `plan.md` 和实际代码 diff；本文件只作为人工导航页。

## 当前验收状态

- AI Self-Acceptance: PASS，见 `validation.md`。
- 用户验收: PASS，用户已回复“人工验收通过，继续往下执行”。
- Simplify: N/A，无产品代码清理，见 `progress.md`。
- Test hardening: N/A，不新增测试文件，见 `progress.md`。
- Retrospective: completed，见 `workflow-record.md` 和 `improvement-candidates.md`。
- 已知缺口: 全量 `npm run acceptance:cdp` 被既有 `rank_threshold` 断言阻断；自动选题专项浏览器验证已通过。
