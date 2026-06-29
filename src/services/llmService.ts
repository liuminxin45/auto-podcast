import type { LLMCallOptions, LLMResponse, PerformanceMetrics } from '../types/llm'
import { LLMError } from '../types/llm'
import { LLM_DEFAULTS } from '../constants/llm'
import { LRUCache } from './llm/cache'
import { TokenBucketRateLimiter } from './llm/rateLimit'
import { MetricsCollector } from './llm/metrics'
import {
  normalizeUrl,
  validateCredentials,
  extractModelIds,
  normalizeError,
  getCacheKey,
  delay,
} from './llm/utils'

class LLMService {
  private cache: LRUCache
  private rateLimiter: TokenBucketRateLimiter
  private metricsCollector: MetricsCollector
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
    const useElectronProxy = this.shouldUseElectronLLMCall()
    console.info('[LLMService] call start', {
      model,
      useElectronProxy,
      timeout,
      maxTokens,
      messageCount: messages.length,
    })

    try {
      if (!useElectronProxy) {
        throw new LLMError('LLM Gateway requires Electron IPC', 'CONFIG')
      }

      const response = await this.callViaElectron({
        apiBase,
        apiKey,
        model,
        messages,
        temperature,
        maxTokens,
        timeout,
      })

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
      if (!this.shouldUseElectronModelFetch()) {
        throw new LLMError('LLM Gateway requires Electron IPC', 'CONFIG')
      }
      const data = await (window as any).electronAPI.llmFetchModels({ apiBase, apiKey })
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
    const {
      apiBase,
      apiKey,
      model,
      messages,
      temperature = LLM_DEFAULTS.TEMPERATURE,
      maxTokens,
      timeout = LLM_DEFAULTS.STREAMING_TIMEOUT,
    } = options

    validateCredentials(apiBase, apiKey)
    await this.rateLimiter.acquire()

    const api = typeof window !== 'undefined' ? (window as any).electronAPI : null
    if (!api?.llmCall || !api?.onLLMStreamChunk || !api?.onLLMStreamDone || !api?.onLLMStreamError) {
      throw new LLMError('LLM Gateway streaming requires Electron IPC', 'CONFIG')
    }

    await new Promise<void>((resolve, reject) => {
      api.onLLMStreamChunk((chunk: string) => onChunk(chunk))
      api.onLLMStreamDone(() => {
        api.removeLLMStreamListeners?.()
        resolve()
      })
      api.onLLMStreamError((error: string) => {
        api.removeLLMStreamListeners?.()
        reject(new LLMError(error || 'LLM stream failed', 'PROVIDER'))
      })

      api.llmCall({
        apiBase: normalizeUrl(apiBase),
        apiKey: apiKey.trim(),
        model,
        messages,
        temperature,
        maxTokens,
        timeout,
        stream: true,
      }).catch((error: any) => {
        api.removeLLMStreamListeners?.()
        reject(normalizeError(error))
      })
    })
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
}

export const llmService = new LLMService()
