const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')
const ConfigManager = require('./configManager')
const { validateNodeOutput } = require('./nodeValidator')

let mainWindow = null
let configManager = null

// Python workflow state
let currentWorkflow = null

// TrendRadar daemon process
let trendradarDaemon = null

const DEFAULT_RADAR_STATE = {
  enabled: false,
  intervalMin: 30,
  keepLast: 500,
  lastRunAt: null,
  lastError: null,
  lastNewCount: 0,
  lastFetchedCount: 0,
  running: false,
  runStartedAt: null,
  contents: []
}

let radarState = { ...DEFAULT_RADAR_STATE }
let radarTimer = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  })

  // Load React app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

// Run Python node as subprocess with timeout and error handling
function runPythonNode(nodeName, state, timeoutMs = 600000) {  // 增加到10分钟
  return new Promise((resolve, reject) => {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3'
    const proc = spawn(pythonPath, ['-m', `nodes.${nodeName}`], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
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

function getRadarCachePath() {
  return path.join(app.getPath('userData'), 'radar-cache.json')
}

function loadRadarCache() {
  try {
    const cachePath = getRadarCachePath()
    if (fs.existsSync(cachePath)) {
      const raw = JSON.parse(fs.readFileSync(cachePath, 'utf-8'))
      return {
        ...DEFAULT_RADAR_STATE,
        ...raw,
        running: false,
        contents: Array.isArray(raw.contents) ? raw.contents : []
      }
    }
  } catch (error) {
    console.warn('Failed to load radar cache:', error)
  }
  return { ...DEFAULT_RADAR_STATE }
}

function saveRadarCache() {
  try {
    const cachePath = getRadarCachePath()
    fs.writeFileSync(cachePath, JSON.stringify({ ...radarState, running: false }, null, 2), 'utf-8')
  } catch (error) {
    console.warn('Failed to save radar cache:', error)
  }
}

function broadcastRadarUpdate() {
  if (mainWindow) {
    mainWindow.webContents.send('radar:update', radarState)
  }
}

function applyRadarDefaults(config = {}) {
  return {
    monitor_enabled: false,
    monitor_interval_min: 30,
    monitor_keep_last: 500,
    ...config
  }
}

function mergeRadarContents(existing, incoming, keepLast) {
  const combined = [...incoming, ...existing]
  const seen = new Set()
  const merged = []
  const limit = Math.max(10, keepLast || 100)
  for (const item of combined) {
    const key = `${item?.url || ''}|${item?.title || ''}|${item?.source || ''}`
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(item)
    if (merged.length >= limit) break
  }
  return merged
}

function scheduleRadar() {
  if (radarTimer) {
    clearInterval(radarTimer)
    radarTimer = null
  }
  if (!radarState.enabled) return
  const intervalMs = Math.max(5, radarState.intervalMin || 30) * 60 * 1000
  radarTimer = setInterval(() => runRadarOnce(), intervalMs)
}

async function runRadarOnce(configOverride = null) {
  // Guard: reset stuck running state after 5 minutes
  if (radarState.running && radarState.runStartedAt) {
    const elapsed = Date.now() - radarState.runStartedAt
    if (elapsed > 5 * 60 * 1000) {
      console.warn('[Radar] Force-resetting stuck running state after', Math.round(elapsed / 1000), 's')
      radarState.running = false
    }
  }
  if (radarState.running) {
    console.warn('[Radar] Already running, skipping')
    return radarState
  }
  const fetchConfig = applyRadarDefaults(
    configOverride || (configManager ? configManager.loadNodeConfig('fetch') : null) || {}
  )

  radarState.intervalMin = fetchConfig.monitor_interval_min || radarState.intervalMin
  radarState.keepLast = fetchConfig.monitor_keep_last || radarState.keepLast
  radarState.running = true
  radarState.runStartedAt = Date.now()
  broadcastRadarUpdate()

  try {
    console.log('[Radar] Running fetch with enabled_sources:', fetchConfig.enabled_sources || '(none, will auto-fill)')
    const state = {
      runtime_config: { fetch: fetchConfig },
      logs: [],
      errors: [],
      fetch_contents: [],
      manual_contents: [],
      raw_contents: []
    }
    const result = await runPythonNode('fetch', state)
    const incoming = Array.isArray(result?.fetch_contents) ? result.fetch_contents : []
    // Log per-source counts
    const sourceCounts = {}
    for (const item of incoming) {
      const src = item?.source || 'unknown'
      sourceCounts[src] = (sourceCounts[src] || 0) + 1
    }
    console.log(`[Radar] Fetched ${incoming.length} items:`, sourceCounts)
    if (result?.logs) {
      for (const log of result.logs) console.log('[Radar:py]', log)
    }
    if (result?.errors?.length) {
      console.warn('[Radar] Errors from fetch node:', result.errors)
    }
    // Count genuinely new items (not duplicates of what we already had)
    const existingKeys = new Set((radarState.contents || []).map(item =>
      `${item?.url || ''}|${item?.title || ''}|${item?.source || ''}`
    ))
    const newCount = incoming.filter(item => {
      const key = `${item?.url || ''}|${item?.title || ''}|${item?.source || ''}`
      return !existingKeys.has(key)
    }).length
    radarState.contents = mergeRadarContents(radarState.contents || [], incoming, radarState.keepLast)
    radarState.lastNewCount = newCount
    radarState.lastFetchedCount = incoming.length
    radarState.lastRunAt = new Date().toISOString()
    radarState.lastError = null
    console.log(`[Radar] New: ${radarState.lastNewCount}, Total fetched: ${incoming.length}, Total stored: ${radarState.contents.length}`)
  } catch (error) {
    console.error('[Radar] Fetch failed:', error.message)
    console.error('[Radar] Stack:', error.stack)
    radarState.lastError = error.message
    radarState.lastNewCount = 0
    radarState.lastFetchedCount = 0
  } finally {
    radarState.running = false
    saveRadarCache()
    broadcastRadarUpdate()
  }
  return radarState
}

function startRadarService(configOverride = null) {
  const fetchConfig = applyRadarDefaults(
    configOverride || (configManager ? configManager.loadNodeConfig('fetch') : null) || {}
  )
  radarState.enabled = true
  radarState.intervalMin = fetchConfig.monitor_interval_min || 30
  radarState.keepLast = fetchConfig.monitor_keep_last || 100
  scheduleRadar()
  saveRadarCache()
  broadcastRadarUpdate()
  runRadarOnce(fetchConfig)
}

function stopRadarService() {
  if (radarTimer) {
    clearInterval(radarTimer)
    radarTimer = null
  }
  radarState.enabled = false
  radarState.running = false
  saveRadarCache()
  broadcastRadarUpdate()
}

// IPC handlers
ipcMain.handle('workflow:create', async (event, config) => {
  if (currentWorkflow && currentWorkflow.status === 'running') {
    throw new Error('A workflow is already running. Please wait for it to complete.')
  }

  const workflowId = Date.now().toString()
  const episodeId = `ep_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '_')}`
  
  currentWorkflow = {
    id: workflowId,
    state: {
      episode_id: episodeId,
      created_at: new Date().toISOString(),
      runtime_config: config || {},
      logs: [],
      errors: [],
      fetch_contents: [],
      manual_contents: [],
      raw_contents: [],
      cleaned_contents: [],
      researched_contents: [],
      selected_topic: {},
      selected_materials: [],
      script: {},
      stages: [],
      audio_segments: [],
      final_audio_path: '',
      audio_metadata: {},
      cover_path: '',
      intro_outro_paths: {},
      storage_info: {},
      rss_path: '',
      publish_status: {},
      subtitle_path: ''
    },
    status: 'running',
    currentNode: null,
    nodeExecutions: {},
    approvals: {}
  }

  if (mainWindow) {
    mainWindow.webContents.send('workflow:update', currentWorkflow)
  }

  setImmediate(() => runWorkflow(workflowId))

  return { workflowId, episodeId }
})

ipcMain.handle('workflow:get', async (event, workflowId) => {
  return currentWorkflow
})

ipcMain.handle('workflow:approve', async (event, workflowId, nodeName, approved, modifiedOutput) => {
  if (approved && modifiedOutput) {
    Object.assign(currentWorkflow.state, modifiedOutput)
  }
  currentWorkflow.approvals = currentWorkflow.approvals || {}
  currentWorkflow.approvals[nodeName] = approved ? 'approved' : 'rejected'
  
  if (approved) {
    // Resume workflow
    runWorkflow(workflowId, nodeName)
  }
  
  return { status: 'ok' }
})

ipcMain.handle('node:getSchema', async (event, nodeName) => {
  return new Promise((resolve, reject) => {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3'
    const proc = spawn(pythonPath, [
      path.join(__dirname, '..', 'scripts', 'extract_node_schemas.py'),
      nodeName
    ], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
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
        reject(new Error(`Failed to get schema for ${nodeName}: ${stderr}`))
      } else {
        try {
          const schema = JSON.parse(stdout)
          resolve(schema)
        } catch (e) {
          reject(new Error(`Failed to parse schema JSON: ${e.message}`))
        }
      }
    })
  })
})

ipcMain.handle('node:getAllSchemas', async (event) => {
  return new Promise((resolve, reject) => {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3'
    const proc = spawn(pythonPath, [
      path.join(__dirname, '..', 'scripts', 'extract_node_schemas.py')
    ], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
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
        reject(new Error(`Failed to get all schemas: ${stderr}`))
      } else {
        try {
          const schemas = JSON.parse(stdout)
          resolve(schemas)
        } catch (e) {
          reject(new Error(`Failed to parse schemas JSON: ${e.message}`))
        }
      }
    })
  })
})

// Config management handlers
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
  return radarState
})

ipcMain.handle('radar:start', async (event, config) => {
  startRadarService(config)
  return radarState
})

ipcMain.handle('radar:stop', async () => {
  stopRadarService()
  return radarState
})

ipcMain.handle('radar:runOnce', async (event, config) => {
  await runRadarOnce(config)
  return radarState
})

ipcMain.handle('radar:clearContents', async () => {
  radarState.contents = []
  radarState.lastNewCount = 0
  radarState.lastFetchedCount = 0
  saveRadarCache()
  broadcastRadarUpdate()
  return radarState
})

ipcMain.handle('radar:updateContents', async (event, contents) => {
  radarState.contents = contents || []
  saveRadarCache()
  broadcastRadarUpdate()
  return radarState
})

// === TrendRadar Daemon Management ===

function startTrendRadarDaemon(intervalMin = 30) {
  if (trendradarDaemon) {
    console.log('[TrendRadar] Daemon already running (PID:', trendradarDaemon.pid, ')')
    return
  }

  const projectRoot = path.join(__dirname, '..')
  const trendradarDir = path.join(projectRoot, 'engine', 'trendradar')
  if (!fs.existsSync(trendradarDir)) {
    console.log('[TrendRadar] Skipping daemon start — engine/trendradar not found (clone the submodule first)')
    return
  }

  const pythonPath = process.platform === 'win32' ? 'python' : 'python3'

  trendradarDaemon = spawn(pythonPath, [
    '-m', 'engine.daemon',
    '--interval', String(intervalMin)
  ], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false
  })

  console.log(`[TrendRadar] Daemon started (PID=${trendradarDaemon.pid}, interval=${intervalMin}min)`)

  trendradarDaemon.stdout.on('data', (data) => {
    const lines = data.toString().trim().split('\n')
    for (const line of lines) {
      console.log('[TrendRadar]', line)
    }
    // Notify frontend of daemon activity
    if (mainWindow) {
      mainWindow.webContents.send('trendradar:log', data.toString())
    }
  })

  trendradarDaemon.stderr.on('data', (data) => {
    console.error('[TrendRadar:err]', data.toString().trim())
  })

  trendradarDaemon.on('close', (code) => {
    console.log(`[TrendRadar] Daemon exited (code=${code})`)
    trendradarDaemon = null
    if (mainWindow) {
      mainWindow.webContents.send('trendradar:status', { status: 'stopped', code })
    }
  })

  trendradarDaemon.on('error', (err) => {
    console.error('[TrendRadar] Daemon spawn error:', err.message)
    trendradarDaemon = null
  })
}

function stopTrendRadarDaemon() {
  if (!trendradarDaemon) return
  console.log('[TrendRadar] Stopping daemon (PID:', trendradarDaemon.pid, ')')
  trendradarDaemon.kill('SIGTERM')
  // Force kill after 5s if not exited
  setTimeout(() => {
    if (trendradarDaemon) {
      trendradarDaemon.kill('SIGKILL')
      trendradarDaemon = null
    }
  }, 5000)
}

ipcMain.handle('trendradar:start', async (event, intervalMin) => {
  startTrendRadarDaemon(intervalMin || 30)
  return { running: !!trendradarDaemon, pid: trendradarDaemon?.pid }
})

ipcMain.handle('trendradar:stop', async () => {
  stopTrendRadarDaemon()
  return { running: false }
})

ipcMain.handle('trendradar:status', async () => {
  // Read daemon status file for detailed info
  const statusPath = path.join(__dirname, '..', 'engine', 'trendradar_data', 'status.json')
  let daemonStatus = { status: 'not_running' }
  try {
    if (fs.existsSync(statusPath)) {
      daemonStatus = JSON.parse(fs.readFileSync(statusPath, 'utf-8'))
    }
  } catch (e) { /* ignore */ }
  return {
    processRunning: !!trendradarDaemon,
    pid: trendradarDaemon?.pid || null,
    ...daemonStatus
  }
})

// Fetch sources management
ipcMain.handle('fetch:getSources', async (event) => {
  return new Promise((resolve, reject) => {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3'
    const proc = spawn(pythonPath, [
      path.join(__dirname, '..', 'scripts', 'get_fetch_sources.py')
    ], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
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

async function runWorkflow(workflowId, resumeFrom = null) {
  // 6-stage creator workflow: 发现 → 整理 → 构思 → 写作 → 制作 → 发布
  // Each stage groups internal sub-nodes
  const nodes = [
    'fetch', 'manual', 'merge',           // 发现 (discover)
    'preprocess',                          // 整理 (organize)
    'research', 'topic_selection',         // 构思 (ideate) — creation studio
    'script',                              // 写作 (write)
    'tts', 'audio_postprocess', 'assets',  // 制作 (produce)
    'review',                              // 发布 (publish) — pre-publish check
    'publish'                              // 发布 (publish) — store + distribute
  ]

  let startIndex = resumeFrom ? nodes.indexOf(resumeFrom) : 0

  for (let i = startIndex; i < nodes.length; i++) {
    const nodeName = nodes[i]
    
    currentWorkflow.currentNode = nodeName
    currentWorkflow.nodeExecutions[nodeName] = {
      status: 'running',
      startedAt: new Date().toISOString()
    }

    if (mainWindow) {
      mainWindow.webContents.send('workflow:update', currentWorkflow)
    }

    try {
      // 加载节点配置
      const nodeConfig = configManager ? configManager.loadNodeConfig(nodeName) : null
      
      // 如果有配置，将其添加到state中传递给Python节点
      if (nodeConfig) {
        currentWorkflow.state.runtime_config = currentWorkflow.state.runtime_config || {}
        currentWorkflow.state.runtime_config[nodeName] = nodeConfig
      }
      
      const startTime = Date.now()
      const result = await runPythonNode(nodeName, currentWorkflow.state)
      const duration = (Date.now() - startTime) / 1000

      if (!result || typeof result !== 'object') {
        throw new Error(`Invalid result from ${nodeName}: expected object, got ${typeof result}`)
      }

      currentWorkflow.state = result
      
      validateNodeOutput(nodeName, result)
      
      currentWorkflow.nodeExecutions[nodeName] = {
        status: 'completed',
        startedAt: currentWorkflow.nodeExecutions[nodeName].startedAt,
        completedAt: new Date().toISOString(),
        duration
      }

      if (result.errors && result.errors.length > 0) {
        console.warn(`Node ${nodeName} completed with errors:`, result.errors)
      }

      if (mainWindow) {
        mainWindow.webContents.send('workflow:update', currentWorkflow)
      }

      // 检查是否需要审批（针对script节点）
      if (nodeName === 'script' && !currentWorkflow.approvals?.script) {
        // 加载script节点配置，检查是否需要审批
        const scriptConfig = configManager ? configManager.loadNodeConfig('script') : null
        console.log('[Approval Check] Script config:', scriptConfig)
        const requireApproval = scriptConfig?.require_approval ?? false
        console.log('[Approval Check] Require approval:', requireApproval)

        if (requireApproval) {
          console.log('[Approval] Pausing workflow for approval')
          currentWorkflow.status = 'waiting_approval'
          currentWorkflow.nodeExecutions[nodeName].status = 'waiting_approval'
          
          if (mainWindow) {
            mainWindow.webContents.send('workflow:update', currentWorkflow)
            // 发送审批请求事件
            console.log('[Approval] Sending needApproval event to frontend')
            mainWindow.webContents.send('workflow:needApproval', {
              workflowId,
              nodeName,
              data: currentWorkflow.state
            })
          }
          return // 暂停工作流，等待审批
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

      if (mainWindow) {
        mainWindow.webContents.send('workflow:update', currentWorkflow)
      }
      return
    }
  }

  currentWorkflow.status = 'completed'
  if (mainWindow) {
    mainWindow.webContents.send('workflow:update', currentWorkflow)
  }
}

app.whenReady().then(() => {
  configManager = new ConfigManager()
  createWindow()

  radarState = loadRadarCache()
  const fetchConfig = applyRadarDefaults(configManager.loadNodeConfig('fetch') || {})
  radarState.intervalMin = fetchConfig.monitor_interval_min || radarState.intervalMin
  radarState.keepLast = fetchConfig.monitor_keep_last || radarState.keepLast
  if (fetchConfig.monitor_enabled) {
    startRadarService(fetchConfig)
  } else {
    radarState.enabled = false
    saveRadarCache()
    broadcastRadarUpdate()
  }

  // Auto-start TrendRadar daemon for background data collection
  const trendradarInterval = fetchConfig.trendradar_interval_min || 30
  startTrendRadarDaemon(trendradarInterval)
})

app.on('before-quit', () => {
  stopTrendRadarDaemon()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
