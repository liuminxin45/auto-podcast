# 需求质量检查清单: NewsNow 固定版本安装与自定义采集能力部署

**目的**: 验证 `spec.md` 是否足以进入计划和实现阶段。
**创建时间**: 2026-06-25
**Feature**: [spec.md](../spec.md)

## 人类审核摘要

- **检查结论**: Pass，规格已覆盖固定版本、同步、overlay、状态检查和失败行为。
- **阻塞项**: N/A。
- **重点风险**: 网络/GitHub 可达性、半初始化目录恢复、overlay 冲突处理。
- **N/A 总览**: UI、设备、Qt、SDK、ServiceBridge 相关检查不适用，因为本任务只改安装和脚本工具链。
- **验证入口**: `.specify/scripts/powershell/validate-checklist.ps1 -FeatureDir specs/002-newsnow-pinned-install`
- **下一步**: 进入 `speckit-plan`。
- **必需人工决策**: N/A。

## 生成策略

- 结构来源：`.specify/templates/checklist-template.md`。
- 规则来源：`.specify/checklist-rules/common.yml`、`new-feature.yml`、`tooling.yml`。
- 证据原则：所有结论来自 `spec.md`、`.specify/feature.json` 和 `.specify/memory/repository-map.md`。

## 需求质量

- [x] CHK001 `.specify/feature.json` 已将任务分为 `new-feature`，因为这是安装与脚本能力扩展。
- [x] CHK002 `needs-routing` 不适用；当前 task_type 为 `new-feature`。
- [x] CHK003 CS1-CS3 可独立理解，分别覆盖 clone、overlay、状态检查。
- [x] CHK004 FR-001 到 FR-007 均是可观察、可审核或可测试行为。
- [x] CHK005 待确认问题为 N/A，规格说明固定版本和边界已明确。

## 工程边界

- [x] CHK006 已识别 `package.json`、`scripts/sync_newsnow.py`、`scripts/newsnow_runtime.js`、`engine/newsnow.lock.json` 和 overlay 目录。
- [x] CHK007 已识别 `npm install`、`npm run sync:newsnow`、`npm run check:newsnow` 的脚本契约。
- [x] CHK008 已记录外部克隆目录不入库、脏改不静默覆盖、overlay 冲突失败。
- [x] CHK008A N/A，本任务不涉及 UI 状态、ServiceBridge 或 CoreRuntime。
- [x] CHK008B N/A，本任务无 UI interaction/action availability。
- [x] CHK008C N/A，本任务不是 Qt UI 迁移。

## 运行时与数据完整性

- [x] CHK009 N/A，本任务不涉及 device/runtime/cache/handle/permission behavior。
- [x] CHK010 已记录命令行输出可中文、JSON 状态 key 保持 ASCII。
- [x] CHK010A N/A，本任务不涉及 ServiceBridge 或 frontend runtime 事实。

## 身份 / 状态 / API 边界

- [x] CHK010D N/A，不涉及设备身份。
- [x] CHK010E N/A，不涉及 UUID 生成。
- [x] CHK010F N/A，不涉及 SDK native id。
- [x] CHK010G N/A，不涉及前端设备操作。
- [x] CHK010H N/A，不涉及 ServiceBridge 缓存。
- [x] CHK010I N/A，不涉及旧 API 迁移。
- [x] CHK010J N/A，不新增生产 debug/test API。
- [x] CHK010K N/A，不新增跨层身份字段。
- [x] CHK010L N/A，不涉及虚拟设备。
- [x] CHK010M 已说明 `engine/newsnow/` 为忽略的外部克隆目录，不作为源码 diff。
- [x] CHK010N N/A，不涉及 frontend/native plugin 安装目录。

## 结构与文件职责

- [x] CHK010B 规格已基于现有 `scripts/`、`engine/` 和 `package.json` 接入点。
- [x] CHK010C 规格要求 overlay 目录与脚本职责分离，避免把自定义能力只放在外部 clone。

## 分流专项就绪度

- [x] CHK011 N/A，本任务不是 migration。
- [x] CHK012 N/A，本任务不是 bugfix；但 CS1 覆盖了当前失败状态。
- [x] CHK013 已说明这是安装/工具链新增能力，并以 clone、lock、overlay 状态为验收信号。
- [x] CHK014 N/A，本任务无 UI 变化。
- [x] CHK014G N/A，本任务无图标、tooltip、按钮、文案或布局变化。
- [x] CHK014D N/A，本任务无 UI parity 或 host-embedded UI。
- [x] CHK014E N/A，本任务无 CSS/layout 修复。
- [x] CHK014H N/A，本任务无 host-embedded frontend UI。
- [x] CHK014F N/A，本任务无截图对齐或 0px 视觉修复。
- [x] CHK014A delivery_profile 为 `standard-bugfix`，适合单仓中等风险工具链变更。
- [x] CHK014B N/A，本任务不是 bugfix 实现前根因证明。
- [x] CHK014C 规格未写死未证实方案，只要求可观察脚本行为。

## 验证

- [x] CHK015 已描述 `npm run sync:newsnow`、`npm run check:newsnow`、`npm install` smoke。
- [x] CHK016 已要求命令级 smoke 和状态 JSON 验证；如无测试框架则说明 N/A。
- [x] CHK017 计划阶段应在脚本变更后重新运行受影响命令。
- [x] CHK018 无法执行的验证需记录 known gap。
- [x] CHK018A 搜索范围限定在 `package.json`、`scripts/`、`engine/` 和相关 fetch source。
- [x] CHK018B N/A，无 UI 验证。
- [x] CHK018C N/A，无 host-embedded frontend plugin。
- [x] CHK018D N/A，无 native plugin。
- [x] CHK018E N/A，无 host CDP 验证需求。
- [x] CHK018F N/A，不是 Qt-to-frontend UI parity。

## 本地 Spec 分支工作流

- [x] CHK019 当前使用本地 Spec branch `002-newsnow-pinned-install`，不需要 remote tracking。
- [x] CHK020 N/A，单仓任务，仅 `auto-podcast` 受影响。
- [x] CHK021 分支完成动作遵循当前工作区策略；本任务未请求 push。
- [x] CHK022 下一阶段遵守 `ai/workflows/task-routing.md` 的 Stage Continuation Contract。

## 说明

- 本检查清单聚焦安装脚本和外部引擎同步，不评价 NewsNow 上游实现质量。
