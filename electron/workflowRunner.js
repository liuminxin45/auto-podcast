/**
 * Workflow Runner — Sequential node execution engine.
 *
 * Extracted from main.js for maintainability.
 * Uses a context-object pattern to access shared dependencies.
 *
 * Features:
 *   - Per-node retry (configurable, default 1 retry for non-LLM nodes)
 *   - Resume-from capability (pass resumeFrom node name)
 *   - Structured logging with orchestrator prefix
 */
const { validateNodeOutput } = require('./nodeValidator')

const NODE_STAGE_LABELS = {
  fetch:             '发现 - 自动采集',
  manual:            '发现 - 手动输入',
  merge:             '整理 - 素材合并',
  preprocess:        '整理 - 内容清洗',
  research:          '构思 - 深度分析',
  topic_selection:   '构思 - 选题决策',
  script:            '写作 - 脚本生成',
  tts:               '制作 - 语音合成',
  audio_postprocess: '制作 - 音频处理',
  assets:            '制作 - 素材生成',
  review:            '发布 - 成品审阅',
  publish:           '发布 - 发布归档',
}

// Nodes that are safe to retry (no side effects or idempotent)
const RETRYABLE_NODES = new Set([
  'fetch', 'manual', 'merge', 'preprocess',
  'research', 'topic_selection', 'script',
  'assets', 'review',
])
const MAX_RETRIES = 1
const RETRY_DELAY_MS = 2000

const PIPELINE_NODES = [
  'fetch', 'manual', 'merge',
  'preprocess',
  'research', 'topic_selection',
  'script',
  'tts', 'audio_postprocess', 'assets',
  'review',
  'publish'
]

/**
 * @param {object} ctx
 * @param {() => Electron.BrowserWindow | null} ctx.getMainWindow
 * @param {() => import('./configManager') | null} ctx.getConfigManager
 * @param {(name: string, state: object, timeout?: number) => Promise<object>} ctx.runPythonNode
 * @param {() => object} ctx.getCurrentWorkflow
 * @param {(wf: object) => void} ctx.setCurrentWorkflow
 */
function create(ctx) {

  function broadcastUpdate() {
    const win = ctx.getMainWindow()
    const wf = ctx.getCurrentWorkflow()
    if (win && wf) win.webContents.send('workflow:update', wf)
  }

  async function run(workflowId, resumeFrom = null) {
    const currentWorkflow = ctx.getCurrentWorkflow()
    if (!currentWorkflow) return

    let startIndex = 0
    if (resumeFrom === 'auto') {
      // Auto-detect resume point from pipeline manifest
      const manifest = currentWorkflow.state?._manifest?.nodes || {}
      for (let i = 0; i < PIPELINE_NODES.length; i++) {
        const entry = manifest[PIPELINE_NODES[i]]
        if (entry && entry.status === 'ok') {
          startIndex = i + 1
        } else {
          break
        }
      }
      if (startIndex > 0) {
        console.log(`[Workflow] Auto-resume: skipping ${startIndex} completed nodes, starting from ${PIPELINE_NODES[startIndex] || 'END'}`)
      }
    } else if (resumeFrom) {
      startIndex = PIPELINE_NODES.indexOf(resumeFrom)
    }
    const workflowStartTime = Date.now()
    const episodeId = currentWorkflow.state.episode_id || 'unknown'

    if (startIndex === 0) {
      const debugMode = currentWorkflow.state.runtime_config?.debug_mode?.enabled ?? false
      const autoExecute = currentWorkflow.state.runtime_config?.auto_execute ?? false
      currentWorkflow.state.logs = currentWorkflow.state.logs || []
      currentWorkflow.state.logs.push(`[Workflow] ========================================`)
      currentWorkflow.state.logs.push(`[Workflow] 工作流启动`)
      currentWorkflow.state.logs.push(`[Workflow] episode_id: ${episodeId}`)
      currentWorkflow.state.logs.push(`[Workflow] 启动时间: ${new Date().toISOString()}`)
      currentWorkflow.state.logs.push(`[Workflow] 共 ${PIPELINE_NODES.length} 个节点待执行`)
      currentWorkflow.state.logs.push(`[Workflow] auto_execute=${autoExecute}`)
      if (debugMode) {
        currentWorkflow.state.logs.push(`[Workflow] ⚡ DEBUG MODE ACTIVE: LLM调用将使用精简Prompt/低 Token限制`)
        currentWorkflow.state.logs.push(`[Workflow]   效果节点: research, topic_selection, script (将根据debug_mode调整行为)`)
      } else {
        currentWorkflow.state.logs.push(`[Workflow] debug_mode=false (正常模式)`)
      }
      currentWorkflow.state.logs.push(`[Workflow] ========================================`)
    }

    const configManager = ctx.getConfigManager()

    for (let i = startIndex; i < PIPELINE_NODES.length; i++) {
      const nodeName = PIPELINE_NODES[i]
      const stageLabel = NODE_STAGE_LABELS[nodeName] || nodeName

      console.log(`[Workflow] Starting node: ${nodeName} (${i+1}/${PIPELINE_NODES.length})`)

      currentWorkflow.currentNode = nodeName
      currentWorkflow.nodeExecutions[nodeName] = {
        status: 'running',
        startedAt: new Date().toISOString()
      }

      currentWorkflow.state.logs = currentWorkflow.state.logs || []
      currentWorkflow.state.logs.push(`[Orchestrator] ----------------------------------------`)
      currentWorkflow.state.logs.push(`[Orchestrator] ▶ 开始节点 [${i+1}/${PIPELINE_NODES.length}]: ${stageLabel}`)
      currentWorkflow.state.logs.push(`[Orchestrator] 节点名: ${nodeName} | 时间: ${new Date().toISOString()}`)

      broadcastUpdate()

      try {
        const nodeConfig = configManager ? configManager.loadNodeConfig(nodeName) : null

        if (nodeConfig) {
          currentWorkflow.state.runtime_config = currentWorkflow.state.runtime_config || {}
          currentWorkflow.state.runtime_config[nodeName] = nodeConfig
        }

        // Preload script config for nodes that need LLM access (research, topic_selection)
        if ((nodeName === 'research' || nodeName === 'topic_selection') && configManager) {
          currentWorkflow.state.runtime_config = currentWorkflow.state.runtime_config || {}
          if (!currentWorkflow.state.runtime_config.script) {
            const scriptConfig = configManager.loadNodeConfig('script')
            if (scriptConfig) {
              currentWorkflow.state.runtime_config.script = scriptConfig
              console.log(`[${nodeName}] Preloaded script config for LLM access (api_key: ${scriptConfig.api_key ? 'SET' : 'NOT SET'})`)
            } else {
              console.log(`[${nodeName}] ⚠ Failed to load script config, LLM analysis will be skipped`)
            }
          } else {
            console.log(`[${nodeName}] Script config already loaded (api_key: ${currentWorkflow.state.runtime_config.script.api_key ? 'SET' : 'NOT SET'})`)
          }
        }

        // Execute node with retry for retryable nodes
        let result = null
        let lastError = null
        const maxAttempts = RETRYABLE_NODES.has(nodeName) ? 1 + MAX_RETRIES : 1

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          try {
            const startTime = Date.now()
            result = await ctx.runPythonNode(nodeName, currentWorkflow.state)
            const duration = (Date.now() - startTime) / 1000
            console.log(`[${nodeName}] Completed in ${duration.toFixed(2)}s${attempt > 1 ? ` (attempt ${attempt})` : ''}`)

            // Print Python logs to console
            if (result.logs && result.logs.length > 0) {
              console.log(`[${nodeName}:py] === Python logs (${result.logs.length} entries) ===`)
              for (const log of result.logs) {
                console.log(`[${nodeName}:py] ${log}`)
              }
            }

            if (!result || typeof result !== 'object') {
              throw new Error(`Invalid result from ${nodeName}: expected object, got ${typeof result}`)
            }

            validateNodeOutput(nodeName, result)

            currentWorkflow.nodeExecutions[nodeName] = {
              status: 'completed',
              startedAt: currentWorkflow.nodeExecutions[nodeName].startedAt,
              completedAt: new Date().toISOString(),
              duration,
              attempts: attempt,
            }
            lastError = null
            break  // success
          } catch (attemptError) {
            lastError = attemptError
            if (attempt < maxAttempts) {
              console.warn(`[${nodeName}] Attempt ${attempt} failed: ${attemptError.message}. Retrying in ${RETRY_DELAY_MS}ms...`)
              currentWorkflow.state.logs = currentWorkflow.state.logs || []
              currentWorkflow.state.logs.push(`[Orchestrator] ⚠ 节点 ${stageLabel} 第${attempt}次执行失败，${RETRY_DELAY_MS/1000}s 后重试...`)
              broadcastUpdate()
              await new Promise(r => setTimeout(r, RETRY_DELAY_MS))
            }
          }
        }

        if (lastError) {
          throw lastError
        }

        if (result.errors && result.errors.length > 0) {
          console.warn(`Node ${nodeName} completed with errors:`, result.errors)
        }

        // Inject orchestration success log
        if (!result.logs) result.logs = []
        const duration = currentWorkflow.nodeExecutions[nodeName].duration
        const nodeErrors = (result.errors || []).filter(e => e.node === nodeName)
        if (nodeErrors.length > 0) {
          result.logs.push(`[Orchestrator] ⚠ 节点完成但有错误: ${stageLabel} | 耗时: ${duration.toFixed(2)}s | 错误数: ${nodeErrors.length}`)
          for (const e of nodeErrors) {
            result.logs.push(`[Orchestrator]   错误详情: ${e.message}`)
          }
        } else {
          result.logs.push(`[Orchestrator] ✓ 节点完成: ${stageLabel} | 耗时: ${duration.toFixed(2)}s`)
        }

        // State snapshot log
        const stateLog = `[Orchestrator] 状态快照: fetch=${result.fetch_contents?.length || 0}, raw=${result.raw_contents?.length || 0}, cleaned=${result.cleaned_contents?.length || 0}, researched=${result.researched_contents?.length || 0}, materials=${result.selected_materials?.length || 0}, stages=${result.stages?.length || 0}`
        console.log(stateLog)
        result.logs.push(stateLog)
        currentWorkflow.state = result

        broadcastUpdate()

        // Approval gate after script node
        if (nodeName === 'script' && !currentWorkflow.approvals?.script) {
          const scriptConfig = configManager ? configManager.loadNodeConfig('script') : null
          const isAutoExecute = currentWorkflow.state?.runtime_config?.auto_execute ?? false
          const requireApproval = isAutoExecute ? false : (scriptConfig?.require_approval ?? false)
          console.log('[Approval Check] require_approval:', requireApproval, '| auto_execute:', isAutoExecute)

          if (requireApproval) {
            console.log('[Approval] Pausing workflow for approval')
            currentWorkflow.status = 'waiting_approval'
            currentWorkflow.nodeExecutions[nodeName].status = 'waiting_approval'

            const win = ctx.getMainWindow()
            if (win) {
              win.webContents.send('workflow:update', currentWorkflow)
              win.webContents.send('workflow:needApproval', {
                workflowId,
                nodeName,
                data: currentWorkflow.state
              })
            }
            return
          } else {
            console.log('[Approval] Auto-approval mode, continuing workflow')
          }
        }
      } catch (error) {
        console.error(`Node ${nodeName} failed:`, error)

        currentWorkflow.nodeExecutions[nodeName] = {
          status: 'failed',
          startedAt: currentWorkflow.nodeExecutions[nodeName].startedAt,
          completedAt: new Date().toISOString(),
          error: error.message,
          errorStack: error.stack
        }
        currentWorkflow.status = 'failed'
        currentWorkflow.state.errors = currentWorkflow.state.errors || []
        currentWorkflow.state.errors.push({
          node: nodeName,
          message: error.message,
          timestamp: new Date().toISOString()
        })
        currentWorkflow.state.logs = currentWorkflow.state.logs || []
        currentWorkflow.state.logs.push(`[Orchestrator] ✗ 节点失败: ${stageLabel}`)
        currentWorkflow.state.logs.push(`[Orchestrator]   错误: ${error.message}`)
        currentWorkflow.state.logs.push(`[Orchestrator]   时间: ${new Date().toISOString()}`)

        broadcastUpdate()
        return
      }
    }

    // Workflow completed successfully
    const workflowDuration = ((Date.now() - workflowStartTime) / 1000).toFixed(1)
    const completedNodes = Object.entries(currentWorkflow.nodeExecutions)
      .filter(([, v]) => v.status === 'completed').length
    const failedNodes = Object.entries(currentWorkflow.nodeExecutions)
      .filter(([, v]) => v.status === 'failed').length
    currentWorkflow.state.logs = currentWorkflow.state.logs || []
    currentWorkflow.state.logs.push(`[Workflow] ========================================`)
    currentWorkflow.state.logs.push(`[Workflow] 工作流完成`)
    currentWorkflow.state.logs.push(`[Workflow] episode_id: ${episodeId}`)
    currentWorkflow.state.logs.push(`[Workflow] 完成时间: ${new Date().toISOString()}`)
    currentWorkflow.state.logs.push(`[Workflow] 总耗时: ${workflowDuration}s`)
    currentWorkflow.state.logs.push(`[Workflow] 节点统计: 完成=${completedNodes}, 失败=${failedNodes}, 共=${PIPELINE_NODES.length}`)
    currentWorkflow.state.logs.push(`[Workflow] ========================================`)
    currentWorkflow.status = 'completed'
    broadcastUpdate()
  }

  return { run, PIPELINE_NODES, NODE_STAGE_LABELS }
}

module.exports = { create }
