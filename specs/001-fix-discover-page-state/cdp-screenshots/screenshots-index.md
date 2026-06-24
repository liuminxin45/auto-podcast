# CDP / Browser Screenshots

## 自动选题追加验证

| 截图 | 场景 | 结果 |
| --- | --- | --- |
| `autotopic-llm-config-enabled.png` | 注入全局 search/text LLM 配置后打开“自动选题”弹窗并填写核心主题 | 未显示“未配置大模型 API”，开始按钮可用 |
| `autotopic-execution-smoke-before.png` | 修复前执行 mock LLM 自动选题 | LLM 已调用且生成推荐日志，但弹窗停留在“处理完成”，未进入定稿页 |
| `autotopic-execution-smoke-after.png` | 修复后执行 mock LLM 自动选题 | 进入“选题定稿”，显示 `AI 推荐了 1 条内容`、`拟入选（1 条）`、`确认选题（1 条）` |
| `autotopic-llm-config-smoke.png` | 早期配置 smoke 截图 | 配置告警缺失路径的中间验证截图 |
| `current-dom-inspect.png` | 页面入口 DOM 探查 | 确认入口文案为“新增节目” |

## 全量 Electron CDP

全量 Electron CDP 验收截图由现有脚本写入 `docs/acceptance/screenshots/2026-06-24T15-21-47-268Z/`，对应报告为 `docs/acceptance/CDP_ACCEPTANCE_REPORT.md`。该全量验收的失败项是既有 `rank_threshold` 断言，不属于自动选题 LLM 配置修复路径。
