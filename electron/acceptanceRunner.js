const fs = require('fs')
const path = require('path')

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

function markdownList(items) {
  if (!items.length) return '- 无'
  return items.map(item => `- ${item}`).join('\n')
}

function toPosixPath(value) {
  return String(value || '').replace(/\\/g, '/')
}

async function runCdpAcceptance({ app, mainWindow, projectRoot }) {
  const webContents = mainWindow.webContents
  const debuggerApi = webContents.debugger
  const startedAt = new Date()
  const stamp = nowStamp()
  const acceptanceDir = path.join(projectRoot, 'docs', 'acceptance')
  const screenshotDir = path.join(acceptanceDir, 'screenshots', stamp)
  const reportPath = path.join(acceptanceDir, 'CDP_ACCEPTANCE_REPORT.md')
  const steps = []
  const assertions = []
  const failures = []
  const screenshots = []
  const consoleErrors = []
  const networkFailures = []
  const exceptions = []

  fs.mkdirSync(screenshotDir, { recursive: true })

  function recordStep(name, status, detail = '') {
    steps.push({ name, status, detail })
    if (status === 'FAIL') failures.push(`${name}: ${detail}`)
  }

  function assert(name, ok, detail = '') {
    assertions.push({ name, ok, detail })
    if (!ok) failures.push(`${name}: ${detail}`)
  }

  function attachListeners() {
    webContents.on('console-message', (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        consoleErrors.push(`${message} (${sourceId}:${line})`)
      }
    })
    webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
      networkFailures.push(`${errorCode} ${errorDescription}: ${validatedURL}`)
    })
    webContents.on('render-process-gone', (_event, details) => {
      exceptions.push(`renderer gone: ${details.reason}`)
    })
    debuggerApi.on('message', (_event, method, params) => {
      if (method === 'Runtime.exceptionThrown') {
        exceptions.push(params?.exceptionDetails?.text || 'Runtime.exceptionThrown')
      }
      if (method === 'Log.entryAdded') {
        const entry = params?.entry
        if (entry?.level === 'error') {
          consoleErrors.push(entry.text || 'Log.entryAdded error')
        }
      }
      if (method === 'Network.loadingFailed') {
        networkFailures.push(`${params?.errorText || 'loadingFailed'}: ${params?.requestId || ''}`)
      }
    })
  }

  async function send(method, params = {}) {
    return debuggerApi.sendCommand(method, params)
  }

  async function evaluate(expression) {
    const response = await send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    })
    if (response.exceptionDetails) {
      throw new Error(response.exceptionDetails.text || 'Runtime.evaluate failed')
    }
    return response.result?.value
  }

  async function screenshot(name) {
    const filePath = path.join(screenshotDir, `${name}.png`)
    const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
    fs.writeFileSync(filePath, Buffer.from(result.data, 'base64'))
    screenshots.push(filePath)
    return filePath
  }

  async function fileInfo(filePath) {
    if (!filePath || !fs.existsSync(filePath)) return { exists: false, size: 0 }
    const stat = fs.statSync(filePath)
    return { exists: true, size: stat.size }
  }

  try {
    attachListeners()
    debuggerApi.attach('1.3')
    await send('Page.enable')
    await send('Runtime.enable')
    await send('Log.enable')
    await send('Network.enable')

    await screenshot('01-home')
    const domState = await evaluate(`(() => ({
      title: document.title,
      body: document.body.innerText,
      hasElectronAPI: !!window.electronAPI,
      hasMediaDevices: !!navigator.mediaDevices?.getUserMedia,
      hasMediaRecorder: typeof MediaRecorder !== 'undefined'
    }))()`)
    assert('首页 DOM 可读取', Boolean(domState?.body?.trim()), `bodyLength=${domState?.body?.length || 0}`)
    assert('未出现剪枝后的精简主路径', !/LeanSettings|精简组件|剪枝/.test(domState?.body || ''), 'DOM 中不应包含剪枝标记')
    assert('Electron API 已注入', Boolean(domState?.hasElectronAPI), 'window.electronAPI 必须存在')
    assert('媒体 API 可用', Boolean(domState?.hasMediaDevices && domState?.hasMediaRecorder), 'getUserMedia 与 MediaRecorder 必须存在')
    recordStep('读取首页 DOM', 'PASS', `title=${domState?.title || ''}`)

    const workflowResult = await evaluate(`(async () => {
      const result = await window.electronAPI.createWorkflow({ autoRun: false, acceptance: true })
      window.__acceptanceWorkflowId = result.workflowId
      return result
    })()`)
    assert('workflow:create 生成 episode_id', Boolean(workflowResult?.workflowId && workflowResult?.episodeId), JSON.stringify(workflowResult))
    recordStep('创建 episode', 'PASS', `workflowId=${workflowResult?.workflowId}, episodeId=${workflowResult?.episodeId}`)

    const discoverWorkflow = await evaluate(`(async () => {
      const id = window.__acceptanceWorkflowId
      let result = await window.electronAPI.trendradarRunOnce({
        platforms_enabled: true,
        rss_enabled: false,
        enabled_platforms: ['toutiao', 'baidu', 'weibo'],
        enabled_rss_feeds: [],
        max_items_per_source: 2,
        filter_method: 'keyword'
      })
      let items = result.fetch_contents || result.items || []
      if (!items.length) {
        result = await window.electronAPI.trendradarRunOnce({
          platforms_enabled: true,
          rss_enabled: false,
          enabled_platforms: ['bilibili-hot-search', 'zhihu', 'douyin'],
          enabled_rss_feeds: [],
          max_items_per_source: 2,
          filter_method: 'keyword'
        })
        items = result.fetch_contents || result.items || []
      }
      await window.electronAPI.updateWorkflowState(id, {
        fetch_contents: items,
        selected_materials: items.slice(0, 1),
        raw_contents: items.slice(0, 1),
        trendradar_meta: result.meta || {},
        discover_ui: {
          selectedCount: Math.min(items.length, 1),
          proceededAt: new Date().toISOString()
        }
      })
      return await window.electronAPI.getWorkflow(id)
    })()`)
    const firstTrendItem = discoverWorkflow?.state?.fetch_contents?.[0]
    assert('TrendRadar 采集写入当前 workflow', Boolean(firstTrendItem?.trendradar_id), JSON.stringify(firstTrendItem || {}))
    assert(
      'TrendRadar 标题编码正常',
      Array.from(firstTrendItem?.title || '').some(char => {
        const code = char.charCodeAt(0)
        return code >= 0x4e00 && code <= 0x9fff
      }),
      String(firstTrendItem?.title || '')
    )
    assert('发现素材采用后写入 selected_materials', Boolean(discoverWorkflow?.state?.selected_materials?.[0]?.trendradar_id), JSON.stringify(discoverWorkflow?.state?.selected_materials || []))
    recordStep('TrendRadar 发现采集与采用', 'PASS', `items=${discoverWorkflow?.state?.fetch_contents?.length || 0}`)
    await screenshot('02-discover-trendradar-state')

    const settingsProbe = await evaluate(`(async () => {
      const configResult = await window.electronAPI.trendradarGetConfig()
      const sourcesResult = await window.electronAPI.trendradarListSources()
      if (!configResult.success) throw new Error(configResult.error || 'trendradarGetConfig failed')
      if (!sourcesResult.success) throw new Error(sourcesResult.error || 'trendradarListSources failed')
      const platformIds = (sourcesResult.sources || [])
        .filter(source => source.kind === 'platform' && source.enabled)
        .map(source => source.id)
        .slice(0, 2)
      const rssIds = (sourcesResult.sources || [])
        .filter(source => source.kind === 'rss' && source.enabled)
        .map(source => source.id)
        .slice(0, 1)
      const keywordConfig = {
        timezone: 'UTC',
        platforms_enabled: true,
        rss_enabled: false,
        enabled_platforms: platformIds,
        enabled_rss_feeds: [],
        max_items_per_source: 1,
        crawler_request_interval: 0,
        rss_request_interval: 0,
        rss_timeout: 5,
        rss_freshness_enabled: false,
        filter_method: 'keyword',
        report_display_mode: 'platform',
        report_mode: 'current',
        rank_threshold: 1,
        max_news_per_keyword: 2,
        sort_by_position_first: true,
        proxy_enabled: false,
        proxy_url: '',
        api_url: '',
        debug: false
      }
      const keywordResult = await window.electronAPI.trendradarRunOnce(keywordConfig)
      const keywordItems = keywordResult.fetch_contents || keywordResult.items || []
      const keywordMetaConfig = keywordResult.meta?.config || {}
      const rssConfig = {
        ...keywordConfig,
        platforms_enabled: false,
        rss_enabled: true,
        enabled_platforms: [],
        enabled_rss_feeds: rssIds,
        rss_freshness_enabled: true,
        freshness_days: 30,
        rss_timeout: 8
      }
      const rssResult = await window.electronAPI.trendradarRunOnce(rssConfig)
      const rssMetaConfig = rssResult.meta?.config || {}
      let aiResult = null
      if (configResult.config?.ai_available && configResult.config?.ai_api_key_set && platformIds.length) {
        aiResult = await window.electronAPI.trendradarRunOnce({
          ...keywordConfig,
          enabled_platforms: platformIds.slice(0, 1),
          max_items_per_source: 1,
          filter_method: 'ai',
          report_display_mode: 'keyword',
          ai_filter_batch_size: 1,
          ai_filter_batch_interval: 0,
          ai_filter_min_score: 0,
          ai_filter_reclassify_threshold: 0.5,
          ai_timeout: 20
        })
      }
      return {
        config: configResult.config,
        platformIds,
        rssIds,
        keyword: {
          success: keywordResult.success,
          count: keywordItems.length,
          first: keywordItems[0] || null,
          meta: keywordResult.meta || {},
          config: keywordMetaConfig,
          sourceIds: Array.from(new Set(keywordItems.map(item => item.source_id)))
        },
        rss: {
          success: rssResult.success,
          count: (rssResult.fetch_contents || rssResult.items || []).length,
          meta: rssResult.meta || {},
          config: rssMetaConfig
        },
        ai: aiResult ? {
          success: aiResult.success,
          count: (aiResult.fetch_contents || aiResult.items || []).length,
          meta: aiResult.meta || {},
          config: aiResult.meta?.config || {}
        } : null
      }
    })()`)
    assert('采集设置读取到平台来源', settingsProbe?.platformIds?.length > 0, JSON.stringify(settingsProbe?.platformIds || []))
    assert('AI 配置已被 TrendRadar 配置视图识别', Boolean(settingsProbe?.config?.ai_available && settingsProbe?.config?.ai_api_key_set), JSON.stringify({
      ai_available: settingsProbe?.config?.ai_available,
      ai_api_key_set: settingsProbe?.config?.ai_api_key_set,
      ai_provider_source: settingsProbe?.config?.ai_provider_source,
      ai_model: settingsProbe?.config?.ai_model,
    }))
    assert('采集设置下发 max_items_per_source', settingsProbe?.keyword?.config?.max_items_per_source === 1, JSON.stringify(settingsProbe?.keyword?.config || {}))
    assert('采集设置下发 enabled_platforms', JSON.stringify(settingsProbe?.keyword?.config?.enabled_platforms || []) === JSON.stringify(settingsProbe?.platformIds || []), JSON.stringify(settingsProbe?.keyword?.config || {}))
    assert('采集设置下发 timezone 并影响时间戳', String(settingsProbe?.keyword?.meta?.generated_at || '').endsWith('+00:00'), settingsProbe?.keyword?.meta?.generated_at || '')
    assert('采集设置下发 rank_threshold', Number(settingsProbe?.keyword?.meta?.rank_highlight_count || 0) >= 1, JSON.stringify(settingsProbe?.keyword?.meta || {}))
    assert('采集设置下发 report_display_mode=platform', settingsProbe?.keyword?.config?.report_display_mode === 'platform', JSON.stringify(settingsProbe?.keyword?.config || {}))
    assert('采集设置下发 RSS 参数', settingsProbe?.rss?.config?.rss_enabled === true && settingsProbe?.rss?.config?.platforms_enabled === false && settingsProbe?.rss?.config?.rss_timeout === 8 && settingsProbe?.rss?.config?.freshness_days === 30, JSON.stringify(settingsProbe?.rss?.config || {}))
    assert('AI 筛选参数下发到 TrendRadar', Boolean(settingsProbe?.ai?.config?.filter_method === 'ai' && settingsProbe?.ai?.config?.ai_filter_batch_size === 1 && settingsProbe?.ai?.config?.ai_filter_min_score === 0), JSON.stringify(settingsProbe?.ai?.config || settingsProbe?.ai || {}))
    recordStep('采集设置参数 live 验证', 'PASS', `platforms=${settingsProbe?.platformIds?.join(',') || ''}, rss=${settingsProbe?.rssIds?.join(',') || 'none'}, aiItems=${settingsProbe?.ai?.count ?? 'skipped'}`)
    await screenshot('02-discover-settings-live')

    const scriptedWorkflow = await evaluate(`(async () => {
      const id = window.__acceptanceWorkflowId
      const patch = {
        selected_topic: {
          title: 'CDP 验收节目',
          description: '用于验证写作、真人录制、音频处理和本地发布闭环'
        },
        script: {
          title: 'CDP 验收节目',
          description: '通过 Electron CDP 自验收生成的测试节目',
          dialogue: [
            { speaker: 'Host A', text: '这是第一段 CDP 自验收脚本。' },
            { speaker: 'Host B', text: '这是第二段，用于确认 stages 与 script 会写入真实 workflow state。' }
          ]
        },
        stages: [
          { id: 'cdp-stage-1', order: 0, speaker: 'Host A', label: '开场', text: '这是第一段 CDP 自验收脚本。', estimated_duration: 3 },
          { id: 'cdp-stage-2', order: 1, speaker: 'Host B', label: '验证', text: '这是第二段，用于确认 stages 与 script 会写入真实 workflow state。', estimated_duration: 4 }
        ]
      }
      await window.electronAPI.updateWorkflowState(id, patch)
      return await window.electronAPI.getWorkflow(id)
    })()`)
    assert('写作状态已保存 script/stages', scriptedWorkflow?.state?.script?.title === 'CDP 验收节目' && scriptedWorkflow?.state?.stages?.length === 2, JSON.stringify(scriptedWorkflow?.state?.script || {}))
    recordStep('写作页保存脚本状态', 'PASS', `stages=${scriptedWorkflow?.state?.stages?.length || 0}`)
    await screenshot('02-script-state')

    const recordingResult = await evaluate(`(async () => {
      const id = window.__acceptanceWorkflowId
      const workflow = await window.electronAPI.getWorkflow(id)
      const episodeId = workflow.state.episode_id
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      const chunks = []
      recorder.ondataavailable = event => { if (event.data && event.data.size > 0) chunks.push(event.data) }
      await new Promise(resolve => {
        recorder.onstop = resolve
        recorder.start(100)
        setTimeout(() => recorder.stop(), 700)
      })
      stream.getTracks().forEach(track => track.stop())
      const blob = new Blob(chunks, { type: recorder.mimeType || mimeType })
      const buffer = await blob.arrayBuffer()
      const saved = await window.electronAPI.saveRecording({
        episodeId,
        segmentId: 'cdp-stage-1',
        mimeType: blob.type || mimeType,
        durationSeconds: 0.7,
        data: buffer
      })
      await window.electronAPI.updateWorkflowState(id, {
        recording_segments: [{
          id: saved.segmentId || 'cdp-stage-1',
          segment_id: 'cdp-stage-1',
          path: saved.path,
          mime_type: saved.mimeType,
          duration_seconds: saved.durationSeconds,
          size: saved.size
        }],
        audio_segments: [{
          index: 0,
          speaker: 'Host A',
          text: '这是第一段 CDP 自验收脚本。',
          path: saved.path,
          duration_seconds: saved.durationSeconds,
          source: 'recording'
        }]
      })
      return { saved, workflow: await window.electronAPI.getWorkflow(id), blobSize: blob.size, blobType: blob.type }
    })()`)
    const recordingPath = recordingResult?.saved?.path
    const recordingFile = await fileInfo(recordingPath)
    assert('真人录制 WebM 已保存', recordingFile.exists && recordingFile.size > 0, `${recordingPath} size=${recordingFile.size}`)
    assert('录音段写入 workflow state', Boolean(recordingResult?.workflow?.state?.recording_segments?.[0]?.path), JSON.stringify(recordingResult?.workflow?.state?.recording_segments || []))
    recordStep('真人录制与保存', 'PASS', `path=${recordingPath}, blobSize=${recordingResult?.blobSize}`)
    await screenshot('03-recording-state')

    const audioWorkflow = await evaluate(`(async () => {
      const id = window.__acceptanceWorkflowId
      await window.electronAPI.runWorkflowNodes(id, ['audio_postprocess', 'assets', 'review'])
      return await window.electronAPI.getWorkflow(id)
    })()`)
    const finalAudioPath = audioWorkflow?.state?.final_audio_path
    const finalAudioFile = await fileInfo(finalAudioPath)
    assert('final_audio_path 存在且文件大于 0', finalAudioFile.exists && finalAudioFile.size > 0, `${finalAudioPath} size=${finalAudioFile.size}`)
    assert('review_summary 已生成', Boolean(audioWorkflow?.state?.review_summary?.checks?.length), JSON.stringify(audioWorkflow?.state?.review_summary || {}))
    recordStep('运行音频生成与 review', 'PASS', `final_audio_path=${finalAudioPath}`)

    const publishWorkflow = await evaluate(`(async () => {
      const id = window.__acceptanceWorkflowId
      await window.electronAPI.runWorkflowNodes(id, ['review', 'publish'])
      return await window.electronAPI.getWorkflow(id)
    })()`)
    const rssPath = publishWorkflow?.state?.rss_path
    const publishDir = publishWorkflow?.state?.storage_info?.base_dir
    const rssFile = await fileInfo(rssPath)
    const publishDirExists = Boolean(publishDir && fs.existsSync(publishDir))
    assert('rss_path 存在且文件大于 0', rssFile.exists && rssFile.size > 0, `${rssPath} size=${rssFile.size}`)
    assert('storage_info.base_dir 存在', publishDirExists, String(publishDir || ''))
    assert('publish_status 标记本地/RSS 成功', publishWorkflow?.state?.publish_status?.platforms?.local === 'success' && publishWorkflow?.state?.publish_status?.platforms?.rss === 'success', JSON.stringify(publishWorkflow?.state?.publish_status || {}))
    recordStep('运行本地发布与 RSS 导出', 'PASS', `rss=${rssPath}, dir=${publishDir}`)
    await screenshot('04-publish-state')

    assert('无前端 console error', consoleErrors.length === 0, markdownList(consoleErrors))
    assert('无 Runtime exception', exceptions.length === 0, markdownList(exceptions))
    assert('无 Network failure', networkFailures.length === 0, markdownList(networkFailures))
  } catch (error) {
    recordStep('CDP 验收执行', 'FAIL', error?.stack || error?.message || String(error))
  } finally {
    try {
      if (debuggerApi.isAttached()) debuggerApi.detach()
    } catch (error) {
      failures.push(`CDP detach failed: ${error?.message || String(error)}`)
    }

    const status = failures.length ? 'FAIL' : 'PASS'
    const endedAt = new Date()
    const report = [
      '# CDP Acceptance Report',
      '',
      `- Status: ${status}`,
      `- Started: ${startedAt.toISOString()}`,
      `- Ended: ${endedAt.toISOString()}`,
      `- Duration: ${Math.round((endedAt.getTime() - startedAt.getTime()) / 1000)}s`,
      `- CDP transport: Electron webContents.debugger`,
      '',
      '## Steps',
      '',
      steps.map(step => `- ${step.status} ${step.name}${step.detail ? `: ${step.detail}` : ''}`).join('\n') || '- 无',
      '',
      '## Assertions',
      '',
      assertions.map(item => `- ${item.ok ? 'PASS' : 'FAIL'} ${item.name}${item.detail ? `: ${item.detail}` : ''}`).join('\n') || '- 无',
      '',
      '## Screenshots',
      '',
      screenshots.map(filePath => `- ${toPosixPath(filePath)}`).join('\n') || '- 无',
      '',
      '## Console Errors',
      '',
      markdownList(consoleErrors),
      '',
      '## Runtime Exceptions',
      '',
      markdownList(exceptions),
      '',
      '## Network Failures',
      '',
      markdownList(networkFailures),
      '',
      '## Failure Reasons',
      '',
      markdownList(failures),
      '',
    ].join('\n')

    fs.writeFileSync(reportPath, report, 'utf-8')
    console.log(`[CDP Acceptance] ${status}: ${reportPath}`)

    if (process.env.CDP_ACCEPTANCE_QUIT !== '0') {
      const exitCode = status === 'PASS' ? 0 : 1
      console.log(`[CDP Acceptance] exiting with code ${exitCode}`)
      app.exit(exitCode)
      process.kill(process.pid, exitCode === 0 ? 'SIGTERM' : 'SIGINT')
    }
  }
}

module.exports = { runCdpAcceptance }
