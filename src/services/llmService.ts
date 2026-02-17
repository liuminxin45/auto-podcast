import type { LLMCallOptions, LLMResponse, ModelsResponse } from '../types/llm'
import { LLMError } from '../types/llm'
import { LLM_DEFAULTS } from '../constants/llm'

class LLMService {
  private useElectronProxy = false

  constructor() {
    this.useElectronProxy = typeof window !== 'undefined' && !!(window as any).electronAPI?.llmCall
  }

  async call(options: LLMCallOptions): Promise<LLMResponse> {
    const {
      apiBase,
      apiKey,
      model,
      messages,
      temperature = LLM_DEFAULTS.TEMPERATURE,
      maxTokens,
      timeout = LLM_DEFAULTS.TIMEOUT,
    } = options

    if (!apiBase || !apiKey) {
      throw new LLMError('Missing API credentials', 'AUTH')
    }

    try {
      if (this.useElectronProxy) {
        return await this.callViaElectron({ apiBase, apiKey, model, messages, temperature, timeout })
      }
      return await this.callViaFetch({ apiBase, apiKey, model, messages, temperature, maxTokens, timeout })
    } catch (error: any) {
      throw this.normalizeError(error)
    }
  }

  async fetchModels(apiBase: string, apiKey: string): Promise<string[]> {
    if (!apiBase || !apiKey) {
      throw new LLMError('Missing API credentials', 'AUTH')
    }

    try {
      if (this.useElectronProxy) {
        const data = await (window as any).electronAPI.llmFetchModels({ apiBase, apiKey })
        return this.extractModelIds(data)
      }

      const baseUrl = apiBase.trim().replace(/\/$/, '')
      const response = await fetch(`${baseUrl}/models`, {
        method: 'GET',
        headers: this.buildHeaders(apiBase, apiKey),
      })

      if (!response.ok) {
        throw new LLMError(`HTTP ${response.status}`, 'NETWORK', { status: response.status })
      }

      const data: ModelsResponse = await response.json()
      return this.extractModelIds(data)
    } catch (error: any) {
      throw this.normalizeError(error)
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
      onProgress?.((i / items.length))

      try {
        const batchResults = await batchFn(batch)
        results.push(...batchResults)
      } catch (error: any) {
        console.error('[LLMService] Batch analysis failed:', error)
        results.push(...batch)
      }

      await this.delay(LLM_DEFAULTS.BATCH_DELAY)
    }

    onProgress?.(1)
    return results
  }

  private async callViaElectron(options: LLMCallOptions): Promise<LLMResponse> {
    const data = await (window as any).electronAPI.llmCall({
      apiBase: options.apiBase.trim(),
      apiKey: options.apiKey.trim(),
      model: options.model,
      messages: options.messages,
      temperature: options.temperature,
    })

    if (!data.choices?.[0]?.message) {
      throw new LLMError('Invalid response format', 'PARSE', { data })
    }

    return data
  }

  private async callViaFetch(options: LLMCallOptions): Promise<LLMResponse> {
    const baseUrl = options.apiBase.trim().replace(/\/$/, '')
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), options.timeout)

    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: this.buildHeaders(options.apiBase, options.apiKey),
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

      return await response.json()
    } finally {
      clearTimeout(timeoutId)
    }
  }

  private buildHeaders(apiBase: string, apiKey: string): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }

    if (apiBase.includes('openai.azure.com')) {
      headers['api-key'] = apiKey
    } else {
      headers['Authorization'] = `Bearer ${apiKey}`
    }

    return headers
  }

  private extractModelIds(data: ModelsResponse): string[] {
    if (!data.data || !Array.isArray(data.data)) {
      throw new LLMError('Invalid models response', 'PARSE', { data })
    }

    return data.data
      .map(model => model.id)
      .filter(id => id && id.trim())
      .sort()
  }

  private normalizeError(error: any): LLMError {
    if (error instanceof LLMError) return error

    if (error.name === 'AbortError') {
      return new LLMError('Request timeout', 'TIMEOUT')
    }

    if (error.message?.includes('fetch')) {
      return new LLMError('Network error', 'NETWORK', { original: error.message })
    }

    return new LLMError(error.message || 'Unknown error', 'UNKNOWN', { original: error })
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

export const llmService = new LLMService()
