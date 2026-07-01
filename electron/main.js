const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')
const ConfigManager = require('./configManager')
const { fetchModels, callLLM, stopLLMGateway } = require('./llmService')
const { PROVIDER_TO_ENGINE, buildTTSConfig, validateProviderConfig, buildStages } = require('./services/providerConfigBuilder')
const { resolvePythonCommand } = require('../scripts/python313')
const { create: createFileService } = require('./services/fileService')
const { create: createRadarService } = require('./radarService')
const { create: createWorkflowRunner } = require('./workflowRunner')

const SPAWN_SHELL = false
const CDP_DEBUG_ENABLED = process.env.CDP_DEBUG === '1' || process.env.CDP_ACCEPTANCE === '1'
const CDP_PORT = process.env.CDP_PORT || process.env.CDP_ACCEPTANCE_PORT || (CDP_DEBUG_ENABLED ? '9222' : '')
const CDP_HOST = process.env.CDP_HOST || '127.0.0.1'
const ENABLE_FAKE_MEDIA = process.env.CDP_ACCEPTANCE === '1' || process.env.CDP_FAKE_MEDIA === '1'

if (CDP_PORT) {
  app.commandLine.appendSwitch('remote-debugging-port', String(CDP_PORT))
  app.commandLine.appendSwitch('remote-debugging-address', String(CDP_HOST))
  console.log(`[CDP] Remote debugging enabled at http://${CDP_HOST}:${CDP_PORT}`)
}

if (ENABLE_FAKE_MEDIA) {
  app.commandLine.appendSwitch('use-fake-device-for-media-stream')
  app.commandLine.appendSwitch('use-fake-ui-for-media-stream')
}

function getPythonSpawnEnv(extra = {}) {
  return {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    ...extra,
  }
}

let pythonCommand = null

function spawnPython(args, options = {}) {
  pythonCommand ??= resolvePythonCommand()
  const [executable, ...prefixArgs] = pythonCommand
  return spawn(executable, [...prefixArgs, ...args], options)
}

let mainWindow = null
let configManager = null
let currentWorkflow = null
let appCloseConfirmed = false
const WORKFLOW_DIR = path.join(__dirname, '..', 'out', 'workflows')
const PROJECT_ROOT = path.join(__dirname, '..')
const EPISODE_SCHEMA_VERSION = 1

function broadcastWorkflowUpdate() {
  if (mainWindow) {
    mainWindow.webContents.send('workflow:update', currentWorkflow)
  }
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function mergeStatePatch(target, patch) {
  if (!isPlainObject(patch)) return target
  for (const [key, value] of Object.entries(patch)) {
    if (isPlainObject(value) && isPlainObject(target[key])) {
      target[key] = mergeStatePatch({ ...target[key] }, value)
    } else {
      target[key] = value
    }
  }
  return target
}

function sanitizePathPart(value, fallback = 'unknown') {
  const safe = String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_+/g, '_')
  return safe || fallback
}

function createInitialState(episodeId, runtimeConfig) {
  return {
    episode_id: episodeId,
    created_at: new Date().toISOString(),
    schema_version: EPISODE_SCHEMA_VERSION,
    preset: {
      id: 'morning_news_brief',
      content_type: 'news_brief',
      num_hosts: 1,
      target_duration_minutes: 6,
      target_duration_minutes_range: '5-8',
      news_item_count: 4,
      news_item_count_range: '3-5',
      tone: 'clear, concise, commute-friendly',
      language: 'zh-CN'
    },
    source_inputs: [],
    runtime_config: runtimeConfig || {},
    logs: [],
    errors: [],
    fetch_contents: [],
    manual_contents: [],
    raw_contents: [],
    cleaned_contents: [],
    researched_contents: [],
    facts: [],
    selected_topic: {},
    selected_topics: [],
    selected_materials: [],
    script: {},
    edited_script: {},
    stages: [],
    voice_segments: [],
    audio_segments: [],
    recording_segments: [],
    final_audio_path: '',
    audio_metadata: {},
    audio_outputs: {},
    audio_report_path: '',
    cover_path: '',
    intro_outro_paths: {},
    review_summary: {},
    storage_info: {},
    rss_path: '',
    publish_status: {},
    publish_outputs: {},
    subtitle_path: '',
    run_report: {},
    discover_meta: {},
    discover_ui: {},
    organize_ui: {},
    episode_brief: {},
    writing_meta: {}
  }
}

function migrateEpisodeState(state) {
  state.schema_version = EPISODE_SCHEMA_VERSION
  state.migration_warnings = Array.isArray(state.migration_warnings) ? state.migration_warnings : []
  state.preset = state.preset || createInitialState(state.episode_id || `ep_${Date.now()}`, {}).preset
  state.source_inputs = Array.isArray(state.source_inputs) ? state.source_inputs : []
  state.facts = Array.isArray(state.facts) ? state.facts : []
  state.selected_topics = Array.isArray(state.selected_topics) ? state.selected_topics : []
  state.edited_script = state.edited_script && typeof state.edited_script === 'object' ? state.edited_script : {}
  state.voice_segments = Array.isArray(state.voice_segments) ? state.voice_segments : []
  state.audio_outputs = state.audio_outputs && typeof state.audio_outputs === 'object' ? state.audio_outputs : {}
  state.publish_outputs = state.publish_outputs && typeof state.publish_outputs === 'object' ? state.publish_outputs : {}
  state.run_report = state.run_report && typeof state.run_report === 'object' ? state.run_report : {}
  state.audio_report_path = state.audio_report_path || ''
  state.tts_source = state.tts_source || ''

  if (state.source_inputs.length === 0) {
    const source = state.selected_materials || state.cleaned_contents || state.raw_contents || state.fetch_contents || state.manual_contents || []
    state.source_inputs = Array.isArray(source) ? source : []
  }

  const hasEditedSegments = Array.isArray(state.edited_script?.segments) && state.edited_script.segments.length > 0
  const legacyStages = Array.isArray(state.stages) ? state.stages : []
  const legacyDialogue = Array.isArray(state.script?.dialogue) ? state.script.dialogue : []
  if (!hasEditedSegments && (legacyStages.length > 0 || legacyDialogue.length > 0)) {
    const source = legacyStages.length > 0
      ? legacyStages
      : legacyDialogue.map((line, index) => ({ id: `seg_${index + 1}`, text: line?.text || '', speaker: line?.speaker || 'Host A' }))
    state.edited_script = {
      id: `${state.episode_id || 'episode'}_edited_migrated`,
      title: state.script?.title || state.selected_topic?.title || '',
      description: state.script?.description || state.selected_topic?.description || '',
      content_type: 'news_brief',
      preset_id: 'morning_news_brief',
      num_hosts: 1,
      language: 'zh-CN',
      segments: source
        .map((item, index) => {
          const text = String(item?.text || '').trim()
          if (!text) return null
          const type = item?.type || (index === 0 ? 'opening' : index === source.length - 1 ? 'closing' : 'news_item')
          return {
            id: String(item?.id || `seg_${index + 1}`),
            type: ['opening', 'news_item', 'context', 'transition', 'closing', 'custom'].includes(type) ? type : 'news_item',
            title: String(item?.title || item?.label || ''),
            text,
            source_fact_ids: Array.isArray(item?.source_fact_ids) ? item.source_fact_ids : [],
            estimated_seconds: Number(item?.estimated_seconds || item?.estimated_duration || 0),
            speaker: String(item?.speaker || 'Host A'),
          }
        })
        .filter(Boolean),
      edited_from: state.script?.id || 'legacy_script',
      edit_mode: 'migration',
    }
    state.migration_warnings.push('legacy script.dialogue/stages migrated to edited_script.segments')
  }

  state.run_report.schema_validation = {
    ok: true,
    errors: [],
    schema_version: EPISODE_SCHEMA_VERSION,
  }
  state.run_report.migration_warnings = state.migration_warnings
  return state
}

function ensureWorkflowDir() {
  fs.mkdirSync(WORKFLOW_DIR, { recursive: true })
}

function workflowFilePath(workflowId) {
  return path.join(WORKFLOW_DIR, `${sanitizePathPart(workflowId)}.json`)
}

function normalizeWorkflow(workflow) {
  if (!workflow || typeof workflow !== 'object') {
    throw new Error('Invalid workflow file')
  }
  const state = workflow.state || createInitialState(workflow.state?.episode_id, {})
  state.runtime_config = state.runtime_config || {}
  state.preset = state.preset || createInitialState(state.episode_id, {}).preset
  state.source_inputs = state.source_inputs || []
  state.logs = state.logs || []
  state.errors = state.errors || []
  state.fetch_contents = state.fetch_contents || []
  state.manual_contents = state.manual_contents || []
  state.raw_contents = state.raw_contents || []
  state.cleaned_contents = state.cleaned_contents || []
  state.researched_contents = state.researched_contents || []
  state.facts = state.facts || []
  state.selected_topic = state.selected_topic || {}
  state.selected_topics = state.selected_topics || []
  state.selected_materials = state.selected_materials || []
  state.script = state.script || {}
  state.edited_script = state.edited_script || {}
  state.stages = state.stages || []
  state.voice_segments = state.voice_segments || []
  state.audio_segments = state.audio_segments || []
  state.recording_segments = state.recording_segments || []
  state.audio_metadata = state.audio_metadata || {}
  state.audio_outputs = state.audio_outputs || {}
  state.audio_report_path = state.audio_report_path || ''
  state.intro_outro_paths = state.intro_outro_paths || {}
  state.review_summary = state.review_summary || {}
  state.storage_info = state.storage_info || {}
  state.publish_status = state.publish_status || {}
  state.publish_outputs = state.publish_outputs || {}
  state.run_report = state.run_report || {}
  state.discover_meta = state.discover_meta || {}
  state.discover_ui = state.discover_ui || {}
  state.organize_ui = state.organize_ui || {}
  state.episode_brief = state.episode_brief || {}
  state.writing_meta = state.writing_meta || {}
  state.episode_id = state.episode_id || `ep_${workflow.id || Date.now()}`
  state.created_at = state.created_at || new Date().toISOString()
  migrateEpisodeState(state)

  return {
    id: String(workflow.id || Date.now()),
    state,
    status: workflow.status || 'draft',
    currentNode: workflow.currentNode || null,
    nodeExecutions: workflow.nodeExecutions || {},
    approvals: workflow.approvals || {}
  }
}

function saveWorkflow(workflow) {
  if (!workflow?.id) return
  ensureWorkflowDir()
  fs.writeFileSync(workflowFilePath(workflow.id), JSON.stringify(normalizeWorkflow(workflow), null, 2), 'utf8')
}

function loadWorkflow(workflowId) {
  const filePath = workflowFilePath(workflowId)
  if (!fs.existsSync(filePath)) return null
  return normalizeWorkflow(JSON.parse(fs.readFileSync(filePath, 'utf8')))
}

function getWorkflowTitle(workflow) {
  return workflow?.state?.selected_topic?.title ||
    workflow?.state?.script?.title ||
    workflow?.state?.episode_title ||
    '未命名节目'
}

function getWorkflowDescription(workflow) {
  return workflow?.state?.selected_topic?.description ||
    workflow?.state?.script?.description ||
    workflow?.state?.episode_description ||
    ''
}

function createWorkflowSummary(workflow) {
  const normalized = normalizeWorkflow(workflow)
  const filePath = workflowFilePath(normalized.id)
  const isSaved = fs.existsSync(filePath)
  let updatedAt = normalized.state.created_at
  try {
    if (isSaved) {
      updatedAt = fs.statSync(filePath).mtime.toISOString()
    }
  } catch {}

  return {
    id: normalized.id,
    episodeId: normalized.state.episode_id,
    title: getWorkflowTitle(normalized),
    description: getWorkflowDescription(normalized),
    status: normalized.status,
    createdAt: normalized.state.created_at,
    updatedAt,
    previewPath: normalized.state.cover_path || '',
    isCurrent: currentWorkflow?.id === normalized.id,
    isSaved
  }
}

function listSavedWorkflows() {
  ensureWorkflowDir()
  const workflows = fs.readdirSync(WORKFLOW_DIR)
    .filter(name => name.endsWith('.json'))
    .map(name => {
      try {
        const workflow = normalizeWorkflow(JSON.parse(fs.readFileSync(path.join(WORKFLOW_DIR, name), 'utf8')))
        if (currentWorkflow?.id === workflow.id) {
          return createWorkflowSummary(currentWorkflow)
        }
        return createWorkflowSummary(workflow)
      } catch (error) {
        console.warn(`[Workflow] Failed to read ${name}:`, error.message)
        return null
      }
    })
    .filter(Boolean)

  if (currentWorkflow && !workflows.some(item => item.id === currentWorkflow.id)) {
    workflows.push(createWorkflowSummary(currentWorkflow))
  }

  return workflows.sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))
}

function loadLatestWorkflow() {
  const workflows = listSavedWorkflows()
  if (workflows.length === 0) return null
  return loadWorkflow(workflows[0].id)
}

function createWindow() {
  appCloseConfirmed = false
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  })

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5174')
    if (process.env.OPEN_DEVTOOLS === '1') {
      mainWindow.webContents.openDevTools()
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.webContents.once('did-finish-load', () => {
    broadcastWorkflowUpdate()
  })

  mainWindow.on('close', (event) => {
    if (appCloseConfirmed || process.env.CDP_ACCEPTANCE === '1') return
    event.preventDefault()
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('app:close-request')
    }
  })

  if (process.env.CDP_ACCEPTANCE === '1') {
    mainWindow.webContents.once('did-finish-load', () => {
      setTimeout(() => {
        const { runCdpAcceptance } = require('./acceptanceRunner')
        runCdpAcceptance({
          app,
          mainWindow,
          projectRoot: path.join(__dirname, '..')
        }).catch((error) => {
          console.error('[CDP Acceptance] Unhandled failure:', error)
          app.quit()
        })
      }, 500)
    })
  }
}

function runPythonNode(nodeName, state, timeoutMs = 600000) {
  return new Promise((resolve, reject) => {
    const proc = spawnPython(['-m', `nodes.${nodeName}`], {
      cwd: path.join(__dirname, '..'),
      env: getPythonSpawnEnv(),
      shell: SPAWN_SHELL
    })

    let stdout = ''
    let stderr = ''
    let killed = false

    const timeout = setTimeout(() => {
      killed = true
      proc.kill('SIGTERM')
      setTimeout(() => proc.kill('SIGKILL'), 5000)
      reject(new Error(`Node ${nodeName} timeout after ${timeoutMs / 1000}s`))
    }, timeoutMs)

    proc.stdout.on('data', (data) => {
      stdout += data.toString()
    })

    proc.stderr.on('data', (data) => {
      stderr += data.toString()
    })

    proc.on('error', (err) => {
      clearTimeout(timeout)
      if (!killed) {
        reject(new Error(`Failed to spawn node ${nodeName}: ${err.message}`))
      }
    })

    proc.on('close', (code) => {
      clearTimeout(timeout)
      if (killed) return

      if (code !== 0) {
        reject(new Error(`Node ${nodeName} exited with code ${code}: ${stderr || 'No error output'}`))
      } else {
        try {
          const result = JSON.parse(stdout)
          resolve(result)
        } catch (e) {
          reject(new Error(`Failed to parse JSON from ${nodeName}: ${e.message}\nOutput: ${stdout.slice(0, 200)}`))
        }
      }
    })

    try {
      proc.stdin.write(JSON.stringify(state))
      proc.stdin.end()
    } catch (err) {
      clearTimeout(timeout)
      proc.kill()
      reject(new Error(`Failed to write input to ${nodeName}: ${err.message}`))
    }
  })
}

const sharedCtx = {
  getMainWindow: () => mainWindow,
  getConfigManager: () => configManager,
  getCurrentWorkflow: () => currentWorkflow,
  setCurrentWorkflow: (workflow) => {
    currentWorkflow = workflow
  },
  runPythonNode
}
const radar = createRadarService(sharedCtx)
const workflowRunner = createWorkflowRunner(sharedCtx)
const fileService = createFileService({
  projectRoot: PROJECT_ROOT,
  getCurrentWorkflow: () => currentWorkflow
})

// IPC handlers
ipcMain.handle('workflow:list', async () => {
  return listSavedWorkflows()
})

ipcMain.handle('workflow:create', async (event, config) => {
  if (currentWorkflow && currentWorkflow.status === 'running') {
    throw new Error('A workflow is already running. Please wait for it to complete.')
  }

  const workflowId = Date.now().toString()
  const episodeId = `ep_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '_')}`
  const shouldAutoRun = config?.autoRun !== false
  const runtimeConfig = { ...(config || {}) }
  delete runtimeConfig.autoRun
  
  currentWorkflow = {
    id: workflowId,
    state: createInitialState(episodeId, runtimeConfig),
    status: shouldAutoRun ? 'running' : 'draft',
    currentNode: null,
    nodeExecutions: {},
    approvals: {}
  }

  broadcastWorkflowUpdate()

  if (shouldAutoRun) {
    setImmediate(() => workflowRunner.run(workflowId))
  }

  return { workflowId, episodeId }
})

ipcMain.handle('workflow:get', async (event, workflowId) => {
  if (!workflowId) return currentWorkflow
  if (currentWorkflow?.id === workflowId) return currentWorkflow
  return loadWorkflow(workflowId)
})

ipcMain.handle('workflow:open', async (event, workflowId) => {
  const workflow = loadWorkflow(workflowId)
  if (!workflow) {
    throw new Error('Workflow not found')
  }
  currentWorkflow = workflow
  broadcastWorkflowUpdate()
  return currentWorkflow
})

ipcMain.handle('workflow:save', async (event, workflowId) => {
  const workflow = currentWorkflow?.id === workflowId ? currentWorkflow : loadWorkflow(workflowId)
  if (!workflow) {
    throw new Error('Workflow not found')
  }
  workflow.state.logs = workflow.state.logs || []
  workflow.state.logs.push(`[Electron] 节目已保存 ${new Date().toISOString()}`)
  if (currentWorkflow?.id === workflow.id) {
    currentWorkflow = workflow
  }
  saveWorkflow(workflow)
  broadcastWorkflowUpdate()
  return currentWorkflow?.id === workflow.id ? currentWorkflow : workflow
})

ipcMain.handle('workflow:close', async (event, workflowId) => {
  if (currentWorkflow?.id === workflowId) {
    currentWorkflow = null
    broadcastWorkflowUpdate()
  }
  return { success: true }
})

ipcMain.handle('app:confirmClose', async () => {
  appCloseConfirmed = true
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.close()
  } else {
    app.quit()
  }
  return { success: true }
})

ipcMain.handle('workflow:updateMeta', async (event, workflowId, meta) => {
  const workflow = currentWorkflow?.id === workflowId ? currentWorkflow : loadWorkflow(workflowId)
  if (!workflow) {
    throw new Error('Workflow not found')
  }

  workflow.state.selected_topic = workflow.state.selected_topic || {}
  workflow.state.script = workflow.state.script || {}
  if (typeof meta?.title === 'string') {
    workflow.state.selected_topic.title = meta.title
    workflow.state.script.title = meta.title
  }
  if (typeof meta?.description === 'string') {
    workflow.state.selected_topic.description = meta.description
    workflow.state.script.description = meta.description
  }
  if (typeof meta?.previewPath === 'string') {
    workflow.state.cover_path = meta.previewPath
  }
  workflow.state.logs = workflow.state.logs || []
  workflow.state.logs.push(`[Electron] 节目信息已更新 ${new Date().toISOString()}`)

  if (currentWorkflow?.id === workflow.id) {
    currentWorkflow = workflow
    broadcastWorkflowUpdate()
  } else {
    saveWorkflow(workflow)
  }

  return workflow
})

ipcMain.handle('workflow:duplicate', async (event, workflowId) => {
  const source = currentWorkflow?.id === workflowId ? currentWorkflow : loadWorkflow(workflowId)
  if (!source) {
    throw new Error('Workflow not found')
  }

  const copied = normalizeWorkflow(JSON.parse(JSON.stringify(source)))
  copied.id = Date.now().toString()
  copied.state.episode_id = `ep_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '_')}`
  copied.state.created_at = new Date().toISOString()
  copied.state.selected_topic = copied.state.selected_topic || {}
  copied.state.script = copied.state.script || {}
  const originalTitle = getWorkflowTitle(source)
  copied.state.selected_topic.title = `${originalTitle} 副本`
  copied.state.script.title = copied.state.selected_topic.title
  copied.state.logs = copied.state.logs || []
  copied.state.logs.push(`[Electron] 从 ${source.id} 复制 ${new Date().toISOString()}`)
  currentWorkflow = copied
  broadcastWorkflowUpdate()
  return currentWorkflow
})

ipcMain.handle('workflow:delete', async (event, workflowId) => {
  if (currentWorkflow?.id === workflowId && currentWorkflow.status === 'running') {
    throw new Error('运行中的节目不能删除')
  }

  const filePath = workflowFilePath(workflowId)
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath)
  }
  if (currentWorkflow?.id === workflowId) {
    currentWorkflow = null
    broadcastWorkflowUpdate()
  }
  return { success: true }
})

ipcMain.handle('workflow:export', async (event, workflowId) => {
  const workflow = currentWorkflow?.id === workflowId ? currentWorkflow : loadWorkflow(workflowId)
  if (!workflow) {
    throw new Error('Workflow not found')
  }

  const defaultName = `${sanitizePathPart(getWorkflowTitle(workflow), workflow.state.episode_id || workflow.id)}.json`
  const result = await dialog.showSaveDialog(mainWindow, {
    title: '导出节目',
    defaultPath: defaultName,
    filters: [{ name: 'PodFlow Studio 节目', extensions: ['json'] }]
  })
  if (result.canceled || !result.filePath) {
    return { success: false, canceled: true }
  }
  fs.writeFileSync(result.filePath, JSON.stringify(normalizeWorkflow(workflow), null, 2), 'utf8')
  return { success: true, path: result.filePath }
})

ipcMain.handle('workflow:import', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '导入节目',
    properties: ['openFile'],
    filters: [{ name: 'PodFlow Studio 节目', extensions: ['json'] }]
  })
  if (result.canceled || !result.filePaths?.[0]) {
    return { success: false, canceled: true }
  }

  const raw = JSON.parse(fs.readFileSync(result.filePaths[0], 'utf8'))
  const imported = normalizeWorkflow(raw.workflow || raw)
  let workflowId = sanitizePathPart(imported.id || Date.now())
  while (fs.existsSync(workflowFilePath(workflowId))) {
    workflowId = `${sanitizePathPart(imported.id || 'imported')}_${Date.now()}`
  }
  imported.id = workflowId
  imported.state.episode_id = imported.state.episode_id || `ep_imported_${Date.now()}`
  imported.state.logs = imported.state.logs || []
  imported.state.logs.push(`[Electron] 从 ${result.filePaths[0]} 导入 ${new Date().toISOString()}`)
  currentWorkflow = imported
  broadcastWorkflowUpdate()
  return { success: true, workflow: currentWorkflow, summary: createWorkflowSummary(currentWorkflow) }
})

ipcMain.handle('workflow:approve', async (event, workflowId, nodeName, approved, modifiedOutput) => {
  if (approved && modifiedOutput) {
    Object.assign(currentWorkflow.state, modifiedOutput)
  }
  currentWorkflow.approvals = currentWorkflow.approvals || {}
  currentWorkflow.approvals[nodeName] = approved ? 'approved' : 'rejected'
  
  if (approved) {
    setImmediate(() => workflowRunner.run(workflowId, nodeName))
  }
  
  return { status: 'ok' }
})

ipcMain.handle('workflow:updateState', async (event, workflowId, patch) => {
  if (!currentWorkflow || currentWorkflow.id !== workflowId) {
    throw new Error('Workflow not found')
  }

  currentWorkflow.state = mergeStatePatch({ ...currentWorkflow.state }, patch || {})
  currentWorkflow.state.logs = currentWorkflow.state.logs || []
  currentWorkflow.state.logs.push(`[Electron] State updated from UI at ${new Date().toISOString()}`)
  broadcastWorkflowUpdate()
  return currentWorkflow
})

ipcMain.handle('workflow:runNodes', async (event, workflowId, nodeNames) => {
  if (!currentWorkflow || currentWorkflow.id !== workflowId) {
    throw new Error('Workflow not found')
  }
  const requested = Array.isArray(nodeNames) ? nodeNames.filter(Boolean) : []
  if (requested.length === 0) {
    throw new Error('No nodes requested')
  }
  if (currentWorkflow.status === 'running') {
    throw new Error('Workflow is already running')
  }

  currentWorkflow.status = 'running'
  currentWorkflow.currentNode = null
  broadcastWorkflowUpdate()
  await workflowRunner.run(workflowId, null, requested)
  return currentWorkflow
})

ipcMain.handle('recording:save', async (event, payload) => {
  return fileService.saveRecording(payload)
})

ipcMain.handle('file:openPath', async (event, targetPath) => {
  return fileService.openPath(targetPath)
})

ipcMain.handle('file:showItemInFolder', async (event, targetPath) => {
  return fileService.showItemInFolder(targetPath)
})

ipcMain.handle('file:readImageAsDataUrl', async (event, targetPath) => {
  return fileService.readImageAsDataUrl(targetPath)
})

ipcMain.handle('config:save', async (event, nodeName, config) => {
  if (!configManager) {
    return { success: false, error: 'Config manager not initialized' }
  }
  return configManager.saveNodeConfig(nodeName, config)
})

ipcMain.handle('config:load', async (event, nodeName) => {
  if (!configManager) {
    return null
  }
  return configManager.loadNodeConfig(nodeName)
})

ipcMain.handle('config:loadAll', async (event) => {
  if (!configManager) {
    return {}
  }
  return configManager.loadAllConfigs()
})

ipcMain.handle('config:delete', async (event, nodeName) => {
  if (!configManager) {
    return { success: false, error: 'Config manager not initialized' }
  }
  return configManager.deleteNodeConfig(nodeName)
})

ipcMain.handle('config:resetAll', async (event) => {
  if (!configManager) {
    return { success: false, error: 'Config manager not initialized' }
  }
  return configManager.resetAllConfigs()
})

ipcMain.handle('radar:getState', async () => {
  return radar.getState()
})

ipcMain.handle('radar:start', async (event, config) => {
  radar.start(config)
  return radar.getState()
})

ipcMain.handle('radar:stop', async () => {
  radar.stop()
  return radar.getState()
})

ipcMain.handle('radar:runOnce', async (event, config) => {
  await radar.runOnce(config)
  return radar.getState()
})

ipcMain.handle('radar:clearContents', async () => {
  return radar.clearContents()
})

ipcMain.handle('radar:updateContents', async (event, contents) => {
  return radar.updateContents(contents)
})

ipcMain.handle('produce:generate', async (event, payload = {}) => {
  const segments = Array.isArray(payload?.segments) ? payload.segments : []
  if (segments.length === 0) {
    throw new Error('没有可生成的稿件段落，请先完成写作内容。')
  }

  const episodeId = payload?.episodeId
    || `ep_${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '_')}`
  const requestedProvider = payload?.voiceProvider || 'edge_tts'

  const baseTtsConfig = (configManager && configManager.loadNodeConfig('tts')) || {}
  const basePostConfig = (configManager && configManager.loadNodeConfig('audio_postprocess')) || {}

  const runtimeTtsConfig = buildTTSConfig(payload, baseTtsConfig)
  const validation = validateProviderConfig(requestedProvider, { ...runtimeTtsConfig, provider: payload?.providerConfig?.provider })

  if (validation.errors.length > 0) {
    throw new Error(validation.errors.join('; '))
  }

  const stages = buildStages(segments)
  if (stages.length === 0) {
    throw new Error('没有可生成的有效文案，请先补充段落内容。')
  }

  let state = {
    episode_id: episodeId,
    stages,
    logs: [],
    errors: [],
    runtime_config: {
      tts: runtimeTtsConfig,
      audio_postprocess: basePostConfig,
    },
    audio_segments: [],
    final_audio_path: '',
    audio_metadata: {},
  }

  const sendProgress = (progress) => {
    event.sender.send('produce:progress', {
      episodeId,
      ...progress,
    })
  }

  try {
    sendProgress({ stage: 'tts', status: 'running', progress: 25, detail: '正在生成语音片段...' })
    state = await runPythonNode('tts', state, 600000)

    sendProgress({ stage: 'audio_postprocess', status: 'running', progress: 70, detail: '正在合并与后处理音频...' })
    state = await runPythonNode('audio_postprocess', state, 600000)

    if (!state?.final_audio_path) {
      const lastError = Array.isArray(state?.errors) && state.errors.length > 0
        ? state.errors[state.errors.length - 1]?.message
        : ''
      throw new Error(lastError || '音频生成失败：未得到最终音频文件。')
    }

    sendProgress({ stage: 'done', status: 'completed', progress: 100, detail: '音频生成完成' })

    return {
      episodeId,
      providerRequested: requestedProvider,
      providerApplied: PROVIDER_TO_ENGINE[requestedProvider] || 'edge-tts',
      warnings: validation.warnings,
      audioSegments: state.audio_segments || [],
      finalAudioPath: state.final_audio_path,
      audioMetadata: state.audio_metadata || {},
      logs: state.logs || [],
      errors: state.errors || [],
    }
  } catch (error) {
    sendProgress({ stage: 'failed', status: 'failed', progress: 100, detail: error?.message || '生成失败' })
    throw error
  }
})

ipcMain.handle('llm:fetchModels', async (event, { apiBase, apiKey }) => {
  try {
    return await fetchModels({ apiBase, apiKey })
  } catch (error) {
    throw new Error(`Failed to fetch models: ${error.message}`)
  }
})

ipcMain.handle('llm:call', async (event, { apiBase, apiKey, model, messages, temperature, maxTokens, timeout, stream }) => {
  try {
    console.log('[LLM][IPC] call start', {
      model,
      stream: !!stream,
      messageCount: Array.isArray(messages) ? messages.length : 0,
      temperature,
      maxTokens,
      timeout,
    })

    return await callLLM({
      apiBase,
      apiKey,
      model,
      messages,
      temperature,
      maxTokens,
      timeout,
      stream,
      eventSender: stream ? event.sender : null
    })
  } catch (error) {
    const rawMessage = String(error?.message || 'Unknown error')
    const normalizedMessage = rawMessage.replace(/^LLM call failed:\s*/i, '')
    console.error('[LLM][IPC] call failed', {
      model,
      stream: !!stream,
      timeout,
      maxTokens,
      message: normalizedMessage,
    })
    throw new Error(normalizedMessage)
  } finally {
    console.log('[LLM][IPC] call end', { model, stream: !!stream })
  }
})

// Fetch sources management
ipcMain.handle('fetch:getSources', async (event) => {
  return new Promise((resolve, reject) => {
    const proc = spawnPython([
      path.join(__dirname, '..', 'scripts', 'get_fetch_sources.py')
    ], {
      cwd: path.join(__dirname, '..'),
      env: getPythonSpawnEnv(),
      shell: SPAWN_SHELL
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (data) => {
      stdout += data.toString()
    })

    proc.stderr.on('data', (data) => {
      stderr += data.toString()
    })

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Failed to get fetch sources: ${stderr}`))
      } else {
        try {
          const sources = JSON.parse(stdout)
          resolve(sources)
        } catch (e) {
          reject(new Error(`Failed to parse sources JSON: ${e.message}`))
        }
      }
    })
  })
})

app.whenReady().then(() => {
  configManager = new ConfigManager()
  currentWorkflow = null
  createWindow()

  radar.loadCache()
  const fetchConfig = radar.applyDefaults(configManager.loadNodeConfig('fetch') || {})
  if (fetchConfig.monitor_enabled) {
    radar.start(fetchConfig, { runImmediately: false })
  } else {
    radar.stop()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopLLMGateway()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
