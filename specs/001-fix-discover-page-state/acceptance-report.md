# 发现页修复验收记录

## 静态与构建

- `npm run verify`：通过。
  - `verify:config` 3/3 passed。
  - `verify:nodes` 11/11 passed；`topic_selection` 和 `script` 对空输入给出预期警告，但节点验证通过。
- `npm run build`：通过。
- `git diff --check`：通过。
- 静态扫描：
  - 未发现 `[DiscoverPanel] fetchContents:` 调试日志。
  - 主流程页保留“返回”tooltip，图标已改为返回箭头。
  - 剩余 `CloseOutlined` 用于关闭节目、弹窗关闭、删除/移除等关闭语义。

## 浏览器自动化验证

验证方式：Vite 浏览器预览 + Playwright + 系统 Chrome。页面地址为 `http://[::1]:5173`。

CDP 说明：本机 `127.0.0.1:9222` 存在异常监听，`/json/version` 和 `/json/list` 请求超时，且 Windows 无法解析到对应 PID 29612；因此本次未使用该端口作为有效 CDP 目标，改用 Playwright 启动系统 Chrome 做前端自测。

截图目录：

- `specs/001-fix-discover-page-state/cdp-screenshots/`

断言结果：

- 新建节目时，mock 的全局雷达旧缓存 `旧新闻-不应出现` 没有出现在发现页。
- 点击“立即采集”后按钮恢复，页面显示“采集完成”提示，不再无限 loading。
- 未配置 LLM 时点击“智能标签”，页面显示配置引导，开关不进入可用分类流程。
- 控制台未再出现 `[DiscoverPanel] fetchContents:` 刷屏日志。
- 自动化期间无 `pageerror`。

已知非本次修复项：

- 浏览器控制台仍有既存 Ant Design 警告：`destroyOnClose` 废弃提示、静态 `message` context 警告。
- Vite 预览存在一个 404 资源请求，未影响本次路径断言。
- 测试数据采集后可能被当前灵敏度/分类筛选隐藏；本次只验收采集动作结束态、节目隔离和依赖配置门禁。

## 追加回归：启动自动采集与渲染循环

用户复测发现进入新节目后疑似自动采集，并出现 `Maximum update depth exceeded`。

追加修复：

- 发现页自动同步候选状态时增加状态签名，只在候选/收集箱/已选内容真实变化时上报，避免空状态反复写回 workflow。
- Electron 启动恢复 `monitor_enabled` 时只恢复监控定时器，不立即执行一次采集；只有用户点击“立即采集”或重新保存开启监控配置时才立刻采集。
- “立即采集”按钮静止态不再使用转圈样式图标，避免未运行时看起来像在采集。

追加验证：

- `npm run build`：通过。
- `npm run verify`：通过。
- 浏览器 smoke：mock 中 `radarRunOnce` 设置为抛错，进入新节目 2.5 秒内未被调用。
- 浏览器 smoke：`Maximum update depth exceeded` 计数为 0。
- 浏览器 smoke：全局雷达旧缓存仍未显示在新节目发现页。

## 追加回归：自动选题 LLM 配置来源

用户复测发现全局 LLM 已配置，但自动选题助手仍提示“未配置大模型 API”，并要求使用 Spec Kit 流程修复。

根因：

- `DiscoverPanel` 打开 `AutoTopicModal` 时将 `llmConfig` 硬编码为 `null`，导致弹窗不读取全局 LLM 配置。
- 自动选题配置校验只检查 `apiKey`，没有与项目现有 `llmConfigResolver` 的 `discover` 能力解析保持一致。

追加修复：

- `DiscoverPanel` 在打开自动选题弹窗前调用 `llmConfigResolver.getLLMConfig('discover')`，优先使用发现/搜索能力配置，并允许回退到全局文本能力配置。
- `AutoTopicModal` 改为校验 `apiKey`、`apiBase`、`model` 三项完整可用后才允许开始自动选题。
- `useAutoTopic` 使用同一套完整配置校验，并将错误引导文案改为 `Settings -> AI 能力接口`。
- 静态扫描确认不再存在 `llmConfig={null}` 或“节点设置中配置”的旧提示。

追加验证：

- `npx tsc --noEmit --pretty false`：通过。
- `npm run build`：通过。
- `npm run acceptance:cdp`：执行过，真实 Electron CDP 启动成功并生成 `docs/acceptance/CDP_ACCEPTANCE_REPORT.md`；结果为 FAIL，失败点是既有 `rank_threshold` 断言，不是自动选题 LLM 配置路径。
- 浏览器专项 smoke：通过。通过系统 Chrome 加载 `http://127.0.0.1:5174`，在页面启动前注入全局 search/text LLM 配置和 mock Electron API，新增节目后打开“自动选题”弹窗。
  - `warningVisible=false`：不再显示“未配置大模型 API”。
  - `startDisabledAfterTopic=false`：填写核心主题后“开始选题”按钮可用，未被 LLM 配置门禁禁用。
  - `pageErrors=[]`。
  - 截图：`specs/001-fix-discover-page-state/cdp-screenshots/autotopic-llm-config-enabled.png`。

追加执行级修复：

- 进一步执行浏览器 smoke 时发现：mock LLM 已调用并返回 1 条入选内容，但弹窗停留在“处理完成/关闭”，没有进入“选题定稿”。
- 根因是 `AutoTopicModal.handleStart` 在 `await execute(config)` 后读取旧闭包里的 `autoTopicState`，无法观察到 hook 完成后的最新 `stage=done`。
- 修复为用 `useEffect` 监听最新 `autoTopicState.stage`、`autoTopicState.error` 和 `isProcessing`，执行成功后自动切换到 `review`；同时在 `stage=done` 时同步 `selectedItems/rejectedItems`，覆盖 0 入选但有淘汰项的结果。

追加执行级验证：

- `npx vitest run src/hooks/__tests__/useAutoTopic.test.tsx --reporter=dot`：8/8 通过。
- 浏览器执行级 smoke：通过。mock `window.electronAPI.llmCall` 返回 1 条 `keep` 结果，点击“开始选题”后：
  - `llmCallCount=1`。
  - `reviewVisible=true`：页面显示 `AI 推荐了 1 条内容`、`拟入选（1 条）`、`确认选题（1 条）`。
  - `errorVisible=false`。
  - `pageErrors=[]`。
  - 截图：`specs/001-fix-discover-page-state/cdp-screenshots/autotopic-execution-smoke-after.png`。
- `npm run build`：通过。

已知未执行项：

- 现有全量 Electron CDP 验收仍被 `rank_threshold` 既有断言阻断；自动选题专项路径已通过浏览器自动化验证。
