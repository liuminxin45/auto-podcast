# 发现页状态与自动选题修复 - 用户验收说明

## 范围

- Feature: `001-fix-discover-page-state`
- 当前阶段: `speckit-acceptance`
- 影响仓库: `auto-podcast`
- 分支策略: local-only；当前工作树仍在 `main`，未提交、未推送。

## 本次可验收内容

1. 新建节目进入发现页时，不继承旧节目的新闻、候选或已选素材。
2. “立即采集”动作结束后恢复按钮状态，并展示成功、失败或超时提示。
3. 未配置 LLM 时，依赖 LLM 的入口会阻止假开启并显示设置引导。
4. 已配置全局 LLM 后，“自动选题”弹窗能识别配置，不再误报“未配置大模型 API”。
5. 自动选题执行成功后会进入“选题定稿”，显示 AI 推荐、拟入选和确认按钮。
6. 返回按钮图标、雷达设置入口图标和发现页 console 刷屏问题已覆盖在既有验收记录中。

## AI 已完成验证

- `npm run verify`: PASS。
- `npx tsc --noEmit --pretty false`: PASS。
- `npx vitest run src/hooks/__tests__/useAutoTopic.test.tsx --reporter=dot`: PASS，8/8。
- `npm run build`: PASS。
- `git diff --check`: PASS。
- 浏览器专项 smoke: PASS。
  - 全局 search/text LLM 配置注入后，自动选题弹窗不再显示“未配置大模型 API”。
  - 填入核心主题后，“开始选题”按钮可用。
- 浏览器执行级 smoke: PASS。
  - mock `window.electronAPI.llmCall` 返回 1 条 `keep`。
  - 点击“开始选题”后，页面进入“选题定稿”，显示 `AI 推荐了 1 条内容`、`拟入选（1 条）`、`确认选题（1 条）`。

证据入口：

- `specs/001-fix-discover-page-state/validation.md`
- `specs/001-fix-discover-page-state/acceptance-report.md`
- `specs/001-fix-discover-page-state/cdp-screenshots/screenshots-index.md`
- `specs/001-fix-discover-page-state/cdp-screenshots/autotopic-execution-smoke-after.png`
- `docs/acceptance/CDP_ACCEPTANCE_REPORT.md`

## 已知缺口

- `npm run acceptance:cdp` 全量 Electron CDP 验收已执行，但报告状态为 FAIL。失败点是既有 `rank_threshold` 断言，不是自动选题 LLM 配置或自动选题执行路径。
- 未对真实外部 LLM 服务做在线调用；本次 AI 自验使用 mock `window.electronAPI.llmCall` 验证应用侧配置读取、调用、解析和 UI 定稿链路。真实模型稳定性仍取决于你配置的模型服务和输出 JSON 质量。

## 用户验收步骤

1. 启动应用。
2. 在 `Settings -> AI 能力接口` 配置全局搜索或文本 LLM，确保 API Key、API Base、Model 均已填写。
3. 新增一个节目，进入发现页。
4. 确认新节目发现页不显示其它节目遗留新闻或已选素材。
5. 点击“自动选题”。
6. 确认弹窗不再出现“未配置大模型 API”。
7. 输入核心主题，例如 `AI 芯片投资`。
8. 点击“开始选题”。
9. 期望结果：
   - 过程页出现采集、过滤、AI 分析日志。
   - 成功后自动进入“选题定稿”。
   - 如果模型返回有效 JSON，页面显示拟入选/拟淘汰内容和“确认选题”按钮。
   - 如果真实模型返回非 JSON 或服务失败，应显示明确错误，而不是卡住。
10. 点击“确认选题”，确认弹窗关闭，并且选择结果回到发现页选中素材。

## 不通过信号

- 全局 LLM 已配置时仍显示“未配置大模型 API”。
- 填写核心主题后“开始选题”仍因 LLM 配置不可用而禁用。
- 点击“开始选题”后 LLM 已返回结果，但页面停在“处理完成/关闭”，没有进入“选题定稿”。
- 自动选题失败后没有错误提示，或按钮/弹窗卡住不可恢复。
- 新节目发现页出现旧节目新闻或旧选中素材。

## 需要你的动作

请按 `acceptance-checklist.md` 进行人工验收。验收后回复：

- `用户确认验收通过`
- 或说明失败项，我会按失败项回到 `speckit-implement` / `speckit-fact-layer` 继续修。
