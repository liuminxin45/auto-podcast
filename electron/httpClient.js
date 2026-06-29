const https = require('https')
const http = require('http')

function gatewayError(statusCode, data) {
  let parsed = null
  try {
    parsed = JSON.parse(data)
  } catch {
    // Keep raw provider/gateway body when it is not JSON.
  }

  const projectError = parsed?.error
  const code = projectError?.code
  const message = projectError?.message || data.slice(0, 200)
  const error = new Error(code ? `${code}: ${message}` : `HTTP ${statusCode}: ${message}`)
  error.statusCode = statusCode
  error.code = code
  error.body = parsed || data
  return error
}

function makeRequest({ url, method = 'GET', headers = {}, body = null, timeout = 30000 }) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url)
    const isHttps = urlObj.protocol === 'https:'
    const client = isHttps ? https : http

    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method,
      headers,
      agent: false
    }

    if (body && method !== 'GET') {
      const bodyStr = typeof body === 'string' ? body : JSON.stringify(body)
      options.headers['Content-Length'] = Buffer.byteLength(bodyStr)
    }

    const req = client.request(options, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve({ statusCode: res.statusCode, body: JSON.parse(data), raw: data })
          } catch (e) {
            resolve({ statusCode: res.statusCode, body: null, raw: data })
          }
        } else {
          reject(gatewayError(res.statusCode, data))
        }
      })
    })

    req.on('error', (e) => {
      reject(new Error(`Request failed: ${e.message}`))
    })

    req.setTimeout(timeout, () => {
      req.destroy()
      reject(new Error(`Request timeout (${timeout}ms)`))
    })

    if (body && method !== 'GET') {
      const bodyStr = typeof body === 'string' ? body : JSON.stringify(body)
      req.write(bodyStr)
    }

    req.end()
  })
}

function makeStreamingRequest({ url, method = 'POST', headers = {}, body = null, timeout = 180000, onChunk, onEnd, onError }) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url)
    const isHttps = urlObj.protocol === 'https:'
    const client = isHttps ? https : http

    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method,
      headers,
      agent: false
    }

    if (body) {
      const bodyStr = typeof body === 'string' ? body : JSON.stringify(body)
      options.headers['Content-Length'] = Buffer.byteLength(bodyStr)
    }

    const req = client.request(options, (res) => {
      let buffer = ''
      let errorBody = ''
      let streamFailed = false
      
      res.on('data', chunk => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          errorBody += chunk.toString()
          return
        }

        buffer += chunk.toString()
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || trimmed === 'data: [DONE]') continue
          if (!trimmed.startsWith('data: ')) continue

          try {
            const json = JSON.parse(trimmed.slice(6))
            if (json.error) {
              streamFailed = true
              const message = json.error.code ? `${json.error.code}: ${json.error.message}` : json.error.message
              if (onError) onError(message)
              reject(new Error(message))
              req.destroy()
              return
            }
            const content = json.choices?.[0]?.delta?.content
            if (content && onChunk) {
              onChunk(content)
            }
          } catch (e) {
            // Ignore parse errors in streaming
          }
        }
      })

      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const error = gatewayError(res.statusCode, errorBody)
          if (onError) onError(error.message)
          reject(error)
          return
        }
        if (streamFailed) return
        if (onEnd) onEnd()
        resolve({ success: true })
      })

      res.on('error', (err) => {
        if (streamFailed) return
        if (onError) onError(err.message)
        reject(err)
      })
    })

    req.on('error', (e) => {
      if (streamFailed) return
      if (onError) onError(e.message)
      reject(new Error(`Request failed: ${e.message}`))
    })

    req.setTimeout(timeout, () => {
      req.destroy()
      const err = new Error(`Request timeout (${timeout}ms)`)
      if (onError) onError(err.message)
      reject(err)
    })

    if (body) {
      const bodyStr = typeof body === 'string' ? body : JSON.stringify(body)
      req.write(bodyStr)
    }

    req.end()
  })
}

module.exports = {
  makeRequest,
  makeStreamingRequest
}
