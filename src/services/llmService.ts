import type { LLMCallOptions, LLMResponse, ModelsResponse, PerformanceMetrics } from '../types/llm'
import { LLMError } from '../types/llm'
import { LLM_DEFAULTS } from '../constants/llm'
import { LRUCache } from './llm/cache'
import { TokenBucketRateLimiter } from './llm/rateLimit'
import { MetricsCollector } from './llm/metrics'
import {
  normalizeUrl,
  validateCredentials,
  buildHeaders,
  extractModelIds,
  normalizeError,
  getCacheKey,
  delay,
} from './llm/utils'

class LLMService {
  private cache: LRUCache
  private rateLimiter: TokenBucketRateLimiter
  private metricsCollector: MetricsCollector
  private electronProxyDisabledForSession = false
  private debugMode = false

  private resolveRequestTimeout(timeout?: number, extraMs = 0): number {
    const requestedTimeout = typeof timeout === 'number' ? timeout : LLM_DEFAULTS.TIMEOUT
    return Math.max(10000, Math.min(35000, requestedTimeout + extraMs))
  }

  constructor() {
    this.cache = new LRUCache(
      LLM_DEFAULTS.CACHE_MAX_SIZE,
      LLM_DEFAULTS.CACHE_TTL
    )
    
    this.rateLimiter = new TokenBucketRateLimiter({
      maxTokens: LLM_DEFAULTS.RATE_LIMIT_MAX_TOKENS,
      refillRate: LLM_DEFAULTS.RATE_LIMIT_REFILL_RATE,
      refillInterval: LLM_DEFAULTS.RATE_LIMIT_REFILL_INTERVAL,
    })
    
    this.metricsCollector = new MetricsCollector()
  }

  setDebugMode(enabled: boolean): void {
    this.debugMode = enabled
    console.info('[LLMService] Debug mode', enabled ? 'ENABLED' : 'DISABLED')
  }

  async call(options: LLMCallOptions): Promise<LLMResponse> {
    let adjustedOptions = { ...options }
    
    if (this.debugMode) {
      adjustedOptions = this.applyMinimalMode(adjustedOptions)
    }

    const {
      apiBase,
      apiKey,
      model,
      messages,
      temperature = LLM_DEFAULTS.TEMPERATURE,
      maxTokens,
      timeout = LLM_DEFAULTS.TIMEOUT,
    } = adjustedOptions

    validateCredentials(apiBase, apiKey)
    await this.rateLimiter.acquire()

    const cacheKey = getCacheKey(options)
    const cached = this.cache.get(cacheKey)
    if (cached) {
      console.log('[LLMService] Cache hit')
      return cached
    }

    const startTime = Date.now()
    const useElectronProxy = this.shouldUseElectronLLMCall() && !this.electronProxyDisabledForSession
    console.info('[LLMService] call start', {
      model,
      useElectronProxy,
      timeout,
      maxTokens,
      messageCount: messages.length,
    })

    try {
      let response: LLMResponse
      if (useElectronProxy) {
        try {
          response = await this.callViaElectron({ apiBase, apiKey, model, messages, temperature, maxTokens, timeout })
        } catch (error: any) {
          const errorMessage = String(error?.message || '')
          const shouldFallbackToFetch =
            /Electron IPC timeout|request timeout|timeout/i.test(errorMessage)
            || error?.code === 'TIMEOUT'
          if (!shouldFallbackToFetch) {
            throw error
          }

          this.electronProxyDisabledForSession = true
          console.warn('[LLMService] Electron IPC timed out, fallback to fetch', { model, timeout })
          response = await this.callViaFetch({ apiBase, apiKey, model, messages, temperature, maxTokens, timeout })
        }
      } else {
        response = await this.callViaFetch({ apiBase, apiKey, model, messages, temperature, maxTokens, timeout })
      }

      const duration = Date.now() - startTime
      this.metricsCollector.recordCall(duration, true)
      this.cache.set(cacheKey, response)
      console.info('[LLMService] call success', { model, duration })

      return response
    } catch (error: any) {
      const duration = Date.now() - startTime
      this.metricsCollector.recordCall(duration, false)
      console.error('[LLMService] call failed', {
        model,
        duration,
        timeout,
        useElectronProxy,
        message: error?.message,
      })
      throw normalizeError(error)
    }
  }

  async fetchModels(apiBase: string, apiKey: string): Promise<string[]> {
    validateCredentials(apiBase, apiKey)

    try {
      if (this.shouldUseElectronModelFetch()) {
        const data = await (window as any).electronAPI.llmFetchModels({ apiBase, apiKey })
        return extractModelIds(data)
      }

      const baseUrl = normalizeUrl(apiBase)
      const response = await fetch(`${baseUrl}/models`, {
        method: 'GET',
        headers: buildHeaders(apiBase, apiKey),
      })

      if (!response.ok) {
        throw new LLMError(`HTTP ${response.status}`, 'NETWORK', { status: response.status })
      }

      const data: ModelsResponse = await response.json()
      return extractModelIds(data)
    } catch (error: any) {
      throw normalizeError(error)
    }
  }

  async batchAnalyze<T>(
    items: T[],
    batchFn: (batch: T[]) => Promise<T[]>,
    onProgress?: (progress: number) => void
  ): Promise<T[]> {
    const results: T[] = []
    const batchSize = LLM_DEFAULTS.BATCH_SIZE

    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize)
      onProgress?.(i / items.length)

      try {
        const batchResults = await batchFn(batch)
        results.push(...batchResults)
      } catch (error: any) {
        console.error('[LLMService] Batch analysis failed:', error)
        results.push(...batch)
      }

      await delay(LLM_DEFAULTS.BATCH_DELAY)
    }

    onProgress?.(1)
    return results
  }

  async callStreaming(
    options: LLMCallOptions,
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const { apiBase, apiKey, model, messages, temperature = LLM_DEFAULTS.TEMPERATURE } = options

    validateCredentials(apiBase, apiKey)
    await this.rateLimiter.acquire()

    const baseUrl = normalizeUrl(apiBase)
    const headers = buildHeaders(apiBase, apiKey)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), LLM_DEFAULTS.STREAMING_TIMEOUT)

    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model,
          messages,
          temperature,
          stream: true,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new LLMError(`HTTP ${response.status}`, 'NETWORK', { status: response.status })
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new LLMError('No response body', 'NETWORK')
      }

      await this.processStreamResponse(reader, onChunk)
    } finally {
      clearTimeout(timeoutId)
    }
  }

  getMetrics(): PerformanceMetrics {
    return this.metricsCollector.getMetrics()
  }

  clearCache(): void {
    this.cache.clear()
  }

  resetMetrics(): void {
    this.metricsCollector.reset()
  }

  private applyMinimalMode(options: LLMCallOptions): LLMCallOptions {
    return {
      ...options,
      maxTokens: Math.min(options.maxTokens || 200, 200),
      messages: options.messages.map(msg => ({
        ...msg,
        content: this.truncateToMinimal(msg.content),
      })),
    }
  }

  private truncateToMinimal(content: string): string {
    if (content.length <= 150) return content
    return content.slice(0, 150)
  }

  private shouldUseElectronLLMCall(): boolean {
    return typeof window !== 'undefined' && !!(window as any).electronAPI?.llmCall
  }

  private shouldUseElectronModelFetch(): boolean {
    return typeof window !== 'undefined' && !!(window as any).electronAPI?.llmFetchModels
  }

  private async callViaElectron(options: LLMCallOptions): Promise<LLMResponse> {
    const ipcTimeout = this.resolveRequestTimeout(options.timeout, 2000)
    const ipcCall = (window as any).electronAPI.llmCall({
      apiBase: normalizeUrl(options.apiBase),
      apiKey: options.apiKey.trim(),
      model: options.model,
      messages: options.messages,
      temperature: options.temperature,
      maxTokens: options.maxTokens,
      timeout: options.timeout,
    })

    let timer: ReturnType<typeof setTimeout> | null = null
    const timeoutGuard = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        reject(new LLMError(`Electron IPC timeout (${ipcTimeout}ms)`, 'TIMEOUT', { timeout: ipcTimeout }))
      }, ipcTimeout)
    })

    let data: LLMResponse
    try {
      data = await Promise.race([ipcCall, timeoutGuard])
    } finally {
      if (timer) {
        clearTimeout(timer)
      }
    }

    if (!data.choices?.[0]?.message) {
      throw new LLMError('Invalid response format', 'PARSE', { data })
    }

    return data
  }

  private async callViaFetch(options: LLMCallOptions): Promise<LLMResponse> {
    const baseUrl = normalizeUrl(options.apiBase)
    const controller = new AbortController()
    const effectiveTimeout = this.resolveRequestTimeout(options.timeout)
    const timeoutId = setTimeout(() => controller.abort(), effectiveTimeout)

    console.info('[LLMService] fetch call start', {
      model: options.model,
      timeout: effectiveTimeout,
      messageCount: options.messages.length,
    })

    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: buildHeaders(options.apiBase, options.apiKey),
        body: JSON.stringify({
          model: options.model,
          messages: options.messages,
          temperature: options.temperature,
          max_tokens: options.maxTokens,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new LLMError(`HTTP ${response.status}`, 'NETWORK', { status: response.status })
      }

      console.info('[LLMService] fetch call success', { model: options.model })
      return await response.json()
    } finally {
      clearTimeout(timeoutId)
    }
  }

  private async processStreamResponse(
    reader: ReadableStreamDefaultReader<Uint8Array>,
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || trimmed === 'data: [DONE]') continue
          if (!trimmed.startsWith('data: ')) continue

          try {
            const json = JSON.parse(trimmed.slice(6))
            const content = json.choices?.[0]?.delta?.content
            if (content) {
              onChunk(content)
            }
          } catch (e) {
            console.warn('[LLMService] Failed to parse SSE chunk:', e)
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }
}

export const llmService = new LLMService()
