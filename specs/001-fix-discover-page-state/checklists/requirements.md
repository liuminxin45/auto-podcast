# 需求质量检查清单: 修复发现页节目状态与交互问题

**目的**: 验证发现页 bugfix 规格是否足以进入实现。
**创建时间**: 2026-06-18
**Feature**: `specs/001-fix-discover-page-state/spec.md`

## 人类审核摘要

- **检查结论**: Pass；用户已给出实际行为、期望行为和复现入口，规格覆盖状态、UI、配置和验证。
- **阻塞项**: N/A。
- **重点风险**: 发现页本地 state 与 workflow state 同步必须避免清掉当前节目真实数据。
- **N/A 总览**: SDK、设备、Qt 迁移、NativePlugin、HostApplication plugin 不适用。
- **验证入口**: `validate-checklist.ps1`、`npm run verify`、`npm run build`、UI/CDP smoke。
- **下一步**: 进入 plan/implement。
- **必需人工决策**: N/A。

## 生成策略

- 结构来源：`.specify/templates/checklist-template.md`。
- 规则来源：`.specify/checklist-rules/common.yml` 与 `.specify/checklist-rules/bugfix.yml`。
- 证据原则：判断来自 `spec.md`、用户输入、`.specify/memory/repository-map.md` 和 `.specify/memory/constitution.md`。

## 需求质量

- [x] CHK001 `spec.md` 已将任务分为 `bugfix`，并说明原因。
- [x] CHK002 `needs-routing` N/A；本任务已明确为 bugfix。
- [x] CHK003 能力场景可以被独立理解，覆盖新节目隔离、loading、LLM 引导和 UI/日志修复。
- [x] CHK004 需求是可观察、可审核或可测试的。
- [x] CHK005 待确认问题为 N/A，原因是用户需求足够具体。

## 工程边界

- [x] CHK006 已识别影响模块：`src/components/DiscoverPanel.tsx`、页面容器、必要 Electron workflow/config 路径。
- [x] CHK007 Public API、SDK、plugin contracts N/A；任务仅影响 Electron/React 工作台 UI 状态。
- [x] CHK008 已记录兼容性和迁移风险：不改公共 API，不改节点协议，发现页 state 以当前节目为边界。
- [x] CHK008A N/A；不涉及 `ServiceBridge`、`CoreRuntime` 或设备权限。
- [x] CHK008B 已覆盖发现页交互可用性：LLM 依赖开关基于配置可用性。
- [x] CHK008C N/A；不是 Qt UI migration。

## 运行时与数据完整性

- [x] CHK009 发现页必须基于当前 workflow state，不使用旧节目缓存作为真实状态。
- [x] CHK010 已记录中文提示和 UTF-8 本地化边界。
- [x] CHK010A N/A；不涉及 ServiceBridge。

## 身份 / 状态 / API 边界

- [x] CHK010D N/A；不涉及设备 UUID。
- [x] CHK010E N/A；不涉及 UUID 生成。
- [x] CHK010F N/A；不涉及 SDK native id。
- [x] CHK010G N/A；不涉及设备操作身份。
- [x] CHK010H N/A；不涉及 ServiceBridge runtime cache。
- [x] CHK010I N/A；不涉及旧 API。
- [x] CHK010J N/A；不涉及生产 Biz exports。
- [x] CHK010K N/A；不涉及跨层设备字段命名。
- [x] CHK010L N/A；不涉及虚拟设备。
- [x] CHK010M 已确认不以 `dist/` 或运行产物作为修复目标。
- [x] CHK010N 已要求修改仓库源码，不修改运行产物。

## 结构与文件职责

- [x] CHK010B 实现前需读取发现页和相邻页面组件。
- [x] CHK010C 如需新增 helper，应放在发现页或既有前端工具边界内。

## 分流专项就绪度

- [x] CHK011 N/A；不是 migration。
- [x] CHK012 bugfix 已包含实际行为、预期行为、复现路径和回归预期。
- [x] CHK013 N/A；不是 new-feature。
- [x] CHK014 UI 设计来源为用户明确需求和现有目标前端约定。
- [x] CHK014G 已完成 UI / UX / 文案依据追踪。
- [x] CHK014D 已要求覆盖空状态、loading、无配置、清空后空闲和图标状态。
- [x] CHK014E 如首轮 UI/CSS 修复失败，需收集 DOM/console/CDP 证据。
- [x] CHK014H N/A；不是 host-embedded frontend plugin。
- [x] CHK014F N/A；不是 0px 视觉对齐任务。
- [x] CHK014A delivery_profile 为 standard-bugfix，匹配 UI 状态与配置依赖风险。
- [x] CHK014B Root Cause Evidence 将在 plan/implement 前由代码阅读补齐。
- [x] CHK014C 规格未预写未证实补丁。

## 验证

- [x] CHK015 已描述 build、test、UI/CDP smoke。
- [x] CHK016 回归验证包括新节目隔离、loading 闭环、LLM 引导、console 不刷屏。
- [x] CHK017 变更后重新运行受影响验证。
- [x] CHK018 无法执行的验证需记录 gap。
- [x] CHK018A 搜索范围限制在 `src/`、`electron/` 与相关发现页路径。
- [x] CHK018B UI 验证优先在真实应用页面执行。
- [x] CHK018C N/A；不是 host-embedded frontend plugin。
- [x] CHK018D N/A；不是 native plugin。
- [x] CHK018E CDP 验证如执行，应记录目标和截图。
- [x] CHK018F N/A；不是 Qt-to-frontend parity。

## 本地 Spec 分支工作流

- [x] CHK019 使用本地 Spec branch `001-fix-discover-page-state`，不需要 remote tracking。
- [x] CHK020 N/A；单仓库任务。
- [x] CHK021 N/A；本次不执行 branch completion。
- [x] CHK022 当前阶段后按 Stage Continuation Contract 继续 plan/implement。

## 说明

- 该清单允许进入实现；没有阻塞澄清。
