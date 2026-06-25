#!/usr/bin/env node
const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')

const ROOT_DIR = path.resolve(__dirname, '..')
const ENGINE_DIR = path.join(ROOT_DIR, 'engine')
const NEWSNOW_DIR = path.join(ENGINE_DIR, 'newsnow')
const LOCK_FILE = path.join(ENGINE_DIR, 'newsnow.lock.json')
const OVERLAY_STATE_FILE = path.join(NEWSNOW_DIR, '.auto-podcast-overlay.json')
const DEFAULT_HOST = process.env.NEWSNOW_HOST || '127.0.0.1'
const DEFAULT_PORT = Number(process.env.NEWSNOW_PORT || 5175)

function log(message) {
  process.stderr.write(`[newsnow_runtime] ${message}\n`)
}

function readJson(filePath, fallback = {}) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'))
  } catch {
    return fallback
  }
}

function commandEnv(extra = {}) {
  const env = { ...process.env }
  for (const key of ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy']) {
    delete env[key]
  }
  return { ...env, NO_PROXY: '*', no_proxy: '*', ...extra }
}

function run(command, args, cwd = NEWSNOW_DIR) {
  log(`${command} ${args.join(' ')}`)
  const result = spawnSync(command, args, {
    cwd,
    env: commandEnv(),
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
    encoding: 'utf8',
  })
  if (result.stdout) process.stderr.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} exited with code ${result.status}`)
  }
  return result.stdout || ''
}

function runQuiet(command, args, cwd = ROOT_DIR) {
  const result = spawnSync(command, args, {
    cwd,
    env: commandEnv(),
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
    encoding: 'utf8',
  })
  if (result.error || result.status !== 0) return ''
  return (result.stdout || '').trim()
}

function versionTuple(value) {
  return String(value || '').replace(/^v/, '').split('.').map(part => Number(part) || 0)
}

function nodeCompatible(requirement, nodeVersion) {
  const match = String(requirement || '').match(/>=\s*([0-9.]+)/)
  if (!match) return true
  const required = versionTuple(match[1])
  const current = versionTuple(nodeVersion)
  for (let i = 0; i < Math.max(required.length, current.length); i += 1) {
    const a = current[i] || 0
    const b = required[i] || 0
    if (a > b) return true
    if (a < b) return false
  }
  return true
}

function localCommit() {
  if (!fs.existsSync(path.join(NEWSNOW_DIR, '.git'))) return ''
  return runQuiet('git', ['rev-parse', 'HEAD'], NEWSNOW_DIR)
}

function packageInfo() {
  return readJson(path.join(NEWSNOW_DIR, 'package.json'), {})
}

function overlayManifests(lock) {
  return (lock.overlays || []).map((overlay) => {
    const overlayPath = path.join(ROOT_DIR, overlay.path || '')
    return {
      id: overlay.id || path.basename(overlayPath),
      version: overlay.version || '',
      path: overlayPath,
      manifest: readJson(path.join(overlayPath, 'manifest.json'), null),
    }
  })
}

function verifyOverlayPatch(patch) {
  const target = path.join(NEWSNOW_DIR, patch.target || '')
  if (!fs.existsSync(target)) return `patch target missing: ${patch.target}`
  const text = fs.readFileSync(target, 'utf8').replace(/\r\n/g, '\n')
  const insert = (patch.insert_lines || []).join('\n').replace(/\r\n/g, '\n')
  if (!insert || !text.includes(insert)) return `patch not applied: ${patch.id || patch.target}`
  return ''
}

function overlayStatus(lock) {
  const manifests = overlayManifests(lock)
  const errors = []
  const overlays = []

  for (const overlay of manifests) {
    if (!overlay.manifest) {
      errors.push(`overlay manifest missing: ${overlay.path}`)
      continue
    }

    const files = overlay.manifest.files || []
    for (const file of files) {
      const target = path.join(NEWSNOW_DIR, file.target || '')
      if (!fs.existsSync(target)) errors.push(`overlay file missing: ${file.target}`)
    }

    const patches = overlay.manifest.text_patches || []
    for (const patch of patches) {
      const error = verifyOverlayPatch(patch)
      if (error) errors.push(error)
    }

    overlays.push({
      id: overlay.manifest.id || overlay.id,
      version: overlay.manifest.version || overlay.version,
      fileCount: files.length,
      patchCount: patches.length,
    })
  }

  const state = readJson(OVERLAY_STATE_FILE, null)
  if (manifests.length && !state) errors.push('overlay state missing')

  return {
    required: manifests.length > 0,
    applied: manifests.length === 0 || errors.length === 0,
    state,
    overlays,
    errors,
  }
}

function runtimeStatus() {
  const lock = readJson(LOCK_FILE, {})
  const pkg = packageInfo()
  const pnpmVersion = runQuiet('pnpm', ['-v'])
  const nodeVersion = process.version
  const dependenciesInstalled = fs.existsSync(path.join(NEWSNOW_DIR, 'node_modules'))
  const built = fs.existsSync(path.join(NEWSNOW_DIR, 'dist', 'output', 'server', 'index.mjs'))
  const apiUrl = `http://${DEFAULT_HOST}:${DEFAULT_PORT}${lock.api_path || '/api/s'}`
  const available = fs.existsSync(path.join(NEWSNOW_DIR, 'package.json'))
  const nodeRequirement = lock.node || '>=20'
  const overlay = available ? overlayStatus(lock) : { required: Boolean((lock.overlays || []).length), applied: false, state: null, overlays: [], errors: [] }
  const blockers = []
  if (!available) blockers.push('engine/newsnow is not cloned')
  if (available && lock.commit && localCommit() !== lock.commit) blockers.push(`NewsNow commit mismatch: expected ${lock.commit}, current ${localCommit() || 'unknown'}`)
  if (available && overlay.required && !overlay.applied) blockers.push(`NewsNow overlay is not applied: ${overlay.errors.join('; ')}`)
  if (!nodeCompatible(nodeRequirement, nodeVersion)) blockers.push(`Node ${nodeRequirement} required, current ${nodeVersion}`)
  if (!pnpmVersion) blockers.push('pnpm is not available on PATH')
  if (available && !dependenciesInstalled) blockers.push('NewsNow dependencies are not installed')

  return {
    success: blockers.length === 0,
    available,
    path: NEWSNOW_DIR,
    repo: lock.repo || 'https://github.com/ourongxing/newsnow.git',
    lockedCommit: lock.commit || '',
    localCommit: localCommit(),
    lockedVersion: lock.version || '',
    packageVersion: pkg.version || '',
    nodeRequirement,
    nodeVersion,
    nodeCompatible: nodeCompatible(nodeRequirement, nodeVersion),
    packageManager: lock.package_manager || pkg.packageManager || 'pnpm',
    overlay,
    overlayApplied: overlay.applied,
    overlayErrors: overlay.errors,
    pnpmAvailable: Boolean(pnpmVersion),
    pnpmVersion,
    dependenciesInstalled,
    built,
    host: DEFAULT_HOST,
    port: DEFAULT_PORT,
    apiPath: lock.api_path || '/api/s',
    apiUrl,
    blocker: blockers.join('; '),
  }
}

function setup() {
  const status = runtimeStatus()
  if (!status.available) {
    throw new Error('engine/newsnow is missing. Run sync_newsnow.py first.')
  }
  if (!status.nodeCompatible) {
    throw new Error(`NewsNow requires Node ${status.nodeRequirement}, current ${status.nodeVersion}`)
  }
  if (!status.pnpmAvailable) {
    throw new Error('pnpm is not available on PATH')
  }
  run('pnpm', ['install', '--frozen-lockfile'])
  return runtimeStatus()
}

function build() {
  const status = runtimeStatus()
  if (!status.dependenciesInstalled) {
    throw new Error('NewsNow dependencies are not installed. Run setup first.')
  }
  run('pnpm', ['run', 'build'])
  return runtimeStatus()
}

function main() {
  const action = process.argv[2] || 'status'
  let result
  try {
    if (action === 'status') result = runtimeStatus()
    else if (action === 'setup') result = { ...setup(), success: true }
    else if (action === 'build') result = { ...build(), success: true }
    else throw new Error(`Unsupported action: ${action}`)
  } catch (error) {
    result = { ...runtimeStatus(), success: false, error: error.message }
  }
  process.stdout.write(`${JSON.stringify(result)}\n`)
  process.exit(result.success ? 0 : 1)
}

main()
