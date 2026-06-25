# Review: NewsNow 固定版本安装与自定义采集能力部署

## 目标

让 `npm install` 能自动准备本地 NewsNow：从 `engine/newsnow.lock.json` 指定的上游仓库和固定 commit 拉取源码，并在同步后应用 Auto-Podcast 维护的自定义数据采集能力。

## 风险与重点

- `engine/newsnow/` 是外部克隆目录，继续保持 `.gitignore`，不能提交上游源码。
- 需要处理“不存在目录”和“半初始化 git 目录但无 HEAD/package.json”两类失败状态。
- 自定义采集能力必须存放在仓库内可审计 overlay 中，不能只存在于被忽略目录。
- 失败时必须明确区分网络、git、脏改、依赖、overlay 冲突。

## Workspace Repository Map

- **workspace_root**: `E:\Neo\auto-podcast`
- **default_base_branch**: `main`
- **repository_map**: `.specify/memory/repository-map.md`

| Repository | Path | Role | Why affected |
|------------|------|------|--------------|
| `auto-podcast` | `.` | `electron-react-python-podcast-workbench` | 修改安装脚本、运行时状态检查和外部引擎 overlay。 |

## 审核入口

- 规格: `spec.md`
- 实现计划: `plan.md`
- 验收准则: `acceptance-rubric.md`
- 需求清单: `checklists/requirements.md`
- 验收记录: `acceptance.md`
- 工作流复盘: `workflow-record.md`
- 下一阶段: `speckit-commit`

完整 AI 执行仍必须读取 `spec.md`、后续 `plan.md`，以及实现阶段列出的精确源文件。
