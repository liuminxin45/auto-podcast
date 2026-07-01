/**
 * Radar Service — Content discovery background fetcher.
 *
 * Extracted from main.js for maintainability.
 * Uses a context-object pattern to access shared dependencies.
 */
const fs = require('fs')
const { app } = require('electron')

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
  lastRunContents: [],
  contents: []
}

/**
 * @param {object} ctx
 * @param {() => Electron.BrowserWindow | null} ctx.getMainWindow
 * @param {() => import('./configManager') | null} ctx.getConfigManager
 * @param {(name: string, state: object, timeout?: number) => Promise<object>} ctx.runPythonNode
 */
function create(ctx) {
  let radarState = { ...DEFAULT_RADAR_STATE }
  let radarTimer = null

  // ── persistence ──────────────────────────────────────────────
  function getCachePath() {
    return require('path').join(app.getPath('userData'), 'radar-cache.json')
  }

  function loadCache() {
    try {
      const p = getCachePath()
      if (fs.existsSync(p)) {
        const raw = JSON.parse(fs.readFileSync(p, 'utf-8'))
        return {
          ...DEFAULT_RADAR_STATE,
          ...raw,
          running: false,
          runStartedAt: null,
          lastRunContents: Array.isArray(raw.lastRunContents) ? raw.lastRunContents : [],
          contents: Array.isArray(raw.contents) ? raw.contents : []
        }
      }
    } catch (err) {
      console.warn('Failed to load radar cache:', err)
    }
    return { ...DEFAULT_RADAR_STATE }
  }

  function saveCache() {
    try {
      fs.writeFileSync(getCachePath(), JSON.stringify({ ...radarState, running: false }, null, 2), 'utf-8')
    } catch (err) {
      console.warn('Failed to save radar cache:', err)
    }
  }

  // ── broadcast ────────────────────────────────────────────────
  function broadcast() {
    const win = ctx.getMainWindow()
    if (win) win.webContents.send('radar:update', radarState)
  }

  // ── helpers ──────────────────────────────────────────────────
  function applyDefaults(config = {}) {
    return { monitor_enabled: false, monitor_interval_min: 30, monitor_keep_last: 500, ...config }
  }

  function mergeContents(existing, incoming, keepLast) {
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

  // ── scheduling ───────────────────────────────────────────────
  function schedule() {
    if (radarTimer) { clearInterval(radarTimer); radarTimer = null }
    if (!radarState.enabled) return
    const ms = Math.max(5, radarState.intervalMin || 30) * 60 * 1000
    radarTimer = setInterval(() => runOnce(), ms)
  }

  // ── core ─────────────────────────────────────────────────────
  async function runOnce(configOverride = null) {
    // Guard: reset stuck running state after 5 min
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

    const cm = ctx.getConfigManager()
    const fetchConfig = applyDefaults(
      configOverride || (cm ? cm.loadNodeConfig('fetch') : null) || {}
    )

    radarState.intervalMin = fetchConfig.monitor_interval_min || radarState.intervalMin
    radarState.keepLast = fetchConfig.monitor_keep_last || radarState.keepLast
    radarState.running = true
    radarState.runStartedAt = Date.now()
    broadcast()

    try {
      console.log('[Radar] Running fetch with enabled_sources:', fetchConfig.enabled_sources || '(none, will auto-fill)')
      const state = {
        runtime_config: { fetch: fetchConfig },
        logs: [], errors: [],
        fetch_contents: [], manual_contents: [], raw_contents: []
      }
      const result = await ctx.runPythonNode('fetch', state)
      const incoming = Array.isArray(result?.fetch_contents) ? result.fetch_contents : []

      const sourceCounts = {}
      for (const item of incoming) {
        const src = item?.source || 'unknown'
        sourceCounts[src] = (sourceCounts[src] || 0) + 1
      }
      console.log(`[Radar] Fetched ${incoming.length} items:`, sourceCounts)
      if (result?.logs) { for (const log of result.logs) console.log('[Radar:py]', log) }
      if (result?.errors?.length) { console.warn('[Radar] Errors from fetch node:', result.errors) }

      const existingKeys = new Set((radarState.contents || []).map(item =>
        `${item?.url || ''}|${item?.title || ''}|${item?.source || ''}`
      ))
      const newCount = incoming.filter(item => {
        const key = `${item?.url || ''}|${item?.title || ''}|${item?.source || ''}`
        return !existingKeys.has(key)
      }).length

      radarState.lastRunContents = incoming
      radarState.contents = mergeContents(radarState.contents || [], incoming, radarState.keepLast)
      radarState.lastNewCount = newCount
      radarState.lastFetchedCount = incoming.length
      radarState.lastRunAt = new Date().toISOString()
      radarState.lastError = null
      console.log(`[Radar] New: ${newCount}, Total fetched: ${incoming.length}, Total stored: ${radarState.contents.length}`)
    } catch (error) {
      console.error('[Radar] Fetch failed:', error.message)
      console.error('[Radar] Stack:', error.stack)
      radarState.lastError = error.message
      radarState.lastNewCount = 0
      radarState.lastFetchedCount = 0
      radarState.lastRunContents = []
    } finally {
      radarState.running = false
      saveCache()
      broadcast()
    }
    return radarState
  }

  function start(configOverride = null, options = {}) {
    const cm = ctx.getConfigManager()
    const fetchConfig = applyDefaults(
      configOverride || (cm ? cm.loadNodeConfig('fetch') : null) || {}
    )
    const runImmediately = options.runImmediately !== false
    radarState.enabled = true
    radarState.intervalMin = fetchConfig.monitor_interval_min || 30
    radarState.keepLast = fetchConfig.monitor_keep_last || 100
    schedule()
    saveCache()
    broadcast()
    if (runImmediately) {
      runOnce(fetchConfig)
    }
  }

  function stop() {
    if (radarTimer) { clearInterval(radarTimer); radarTimer = null }
    radarState.enabled = false
    radarState.running = false
    saveCache()
    broadcast()
  }

  // ── public API ───────────────────────────────────────────────
  return {
    getState: () => radarState,
    loadCache: () => { radarState = loadCache(); return radarState },
    saveCache,
    broadcast,
    applyDefaults,
    runOnce,
    start,
    stop,
    clearContents: () => {
      radarState.contents = []
      radarState.lastRunContents = []
      radarState.lastNewCount = 0
      radarState.lastFetchedCount = 0
      saveCache()
      broadcast()
      return radarState
    },
    updateContents: (contents) => {
      radarState.contents = contents || []
      saveCache()
      broadcast()
      return radarState
    },
  }
}

module.exports = { create, DEFAULT_RADAR_STATE }
