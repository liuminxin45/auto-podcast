#!/usr/bin/env node

const http = require('node:http')
const net = require('node:net')
const path = require('node:path')
const { spawn, spawnSync } = require('node:child_process')

const projectRoot = path.resolve(__dirname, '..')
const args = process.argv.slice(2)
const withCdp = args.includes('--cdp')
const preferredPort = Number(
  readArgValue('--port') || process.env.VITE_PORT || process.env.PORT || 5174
)
const cdpPort = String(readArgValue('--cdp-port') || process.env.CDP_PORT || 9222)

let shuttingDown = false
let viteProcess = null
let electronProcess = null

function readArgValue(name) {
  const index = args.indexOf(name)
  if (index === -1) return null
  return args[index + 1] || null
}

function npmBin(name) {
  return path.join(
    projectRoot,
    'node_modules',
    '.bin',
    process.platform === 'win32' ? `${name}.cmd` : name
  )
}

function buildEnv(extra = {}) {
  return { ...process.env, ...extra }
}

function findListeningPids(port) {
  const pids = new Set()
  if (process.platform === 'win32') {
    const result = spawnSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8' })
    const output = `${result.stdout || ''}\n${result.stderr || ''}`
    for (const line of output.split(/\r?\n/)) {
      const columns = line.trim().split(/\s+/)
      if (columns.length < 5) continue
      const localAddress = columns[1] || ''
      const state = columns[3] || ''
      const pid = columns[4] || ''
      if (!localAddress.endsWith(`:${port}`)) continue
      if (state.toUpperCase() !== 'LISTENING') continue
      if (pid && pid !== String(process.pid)) pids.add(pid)
    }
    return Array.from(pids)
  }

  const result = spawnSync('sh', ['-lc', `lsof -tiTCP:${port} -sTCP:LISTEN 2>/dev/null || true`], {
    encoding: 'utf8',
  })
  for (const pid of String(result.stdout || '').split(/\s+/).filter(Boolean)) {
    if (pid !== String(process.pid)) pids.add(pid)
  }
  return Array.from(pids)
}

function isTcpPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(port, '127.0.0.1')
  })
}

async function chooseVitePort(startPort) {
  for (let port = startPort; port < startPort + 50; port += 1) {
    if (await isTcpPortFree(port)) {
      if (port !== startPort) {
        const pids = findListeningPids(startPort)
        const owner = pids.length > 0 ? `，占用 PID: ${pids.join(', ')}` : ''
        console.log(`[dev] 端口 ${startPort} 已被占用${owner}，改用 ${port}`)
      }
      return port
    }
  }
  throw new Error(`未找到可用 Vite 端口，已尝试 ${startPort}-${startPort + 49}`)
}

async function chooseCdpPort(startPort) {
  const start = Number(startPort)
  for (let port = start; port < start + 50; port += 1) {
    if (await isTcpPortFree(port)) {
      if (port !== start) {
        const pids = findListeningPids(start)
        const owner = pids.length > 0 ? `，占用 PID: ${pids.join(', ')}` : ''
        console.log(`[dev] CDP 端口 ${start} 已被占用${owner}，改用 ${port}`)
      }
      return String(port)
    }
  }
  throw new Error(`未找到可用 CDP 端口，已尝试 ${start}-${start + 49}`)
}

function isHttpReady(url) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume()
      resolve(response.statusCode >= 200 && response.statusCode < 500)
    })
    request.on('error', () => resolve(false))
    request.setTimeout(1000, () => {
      request.destroy()
      resolve(false)
    })
  })
}

async function waitForHttp(url, timeoutMs) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (await isHttpReady(url)) return true
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  return false
}

function killProcessTree(child) {
  if (!child || !child.pid) return
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T'], { stdio: 'ignore' })
    return
  }
  spawnSync('sh', ['-lc', `kill -TERM -${child.pid} 2>/dev/null || kill -TERM ${child.pid} 2>/dev/null || true`], {
    stdio: 'ignore',
  })
}

function shutdown(code = 0) {
  if (shuttingDown) return
  shuttingDown = true
  killProcessTree(electronProcess)
  killProcessTree(viteProcess)
  process.exit(code)
}

async function main() {
  const vitePort = await chooseVitePort(preferredPort)
  const viteUrl = `http://127.0.0.1:${vitePort}`
  const resolvedCdpPort = withCdp ? await chooseCdpPort(cdpPort) : ''

  console.log(`[dev] 启动 Vite: ${viteUrl}`)
  viteProcess = spawn(npmBin('vite'), ['--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'], {
    cwd: projectRoot,
    env: buildEnv({ VITE_PORT: String(vitePort) }),
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })

  viteProcess.on('exit', (code) => {
    if (!shuttingDown) {
      console.error(`[dev] Vite 已退出，code=${code ?? 1}`)
      shutdown(code ?? 1)
    }
  })

  const ready = await waitForHttp(viteUrl, 60000)
  if (!ready) {
    console.error(`[dev] Vite 未在 60 秒内就绪: ${viteUrl}`)
    shutdown(1)
  }

  console.log(`[dev] 启动 Electron，页面地址: ${viteUrl}`)
  electronProcess = spawn(npmBin('electron'), ['.'], {
    cwd: projectRoot,
    env: buildEnv({
      NODE_ENV: 'development',
      VITE_DEV_SERVER_URL: viteUrl,
      ...(withCdp
        ? {
            CDP_DEBUG: '1',
            CDP_PORT: resolvedCdpPort,
            CDP_FAKE_MEDIA: process.env.CDP_FAKE_MEDIA || '1',
          }
        : {}),
    }),
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })

  electronProcess.on('exit', (code) => {
    if (!shuttingDown) shutdown(code ?? 0)
  })
  electronProcess.on('error', (error) => {
    console.error(`[dev] Electron 启动失败: ${error.message}`)
    shutdown(1)
  })
}

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))

main().catch((error) => {
  console.error(`[dev] ${error.stack || error.message}`)
  shutdown(1)
})
