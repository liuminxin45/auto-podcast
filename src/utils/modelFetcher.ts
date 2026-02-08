/**
 * Fetch available models from OpenAI-compatible API
 */

export interface ModelInfo {
  id: string
  object: string
  created?: number
  owned_by?: string
}

export interface ModelsResponse {
  object: string
  data: ModelInfo[]
}

/**
 * Fetch models from OpenAI-compatible API
 */
export async function fetchModels(apiBase: string, apiKey: string): Promise<string[]> {
  try {
    // 标准化API Base URL
    const baseUrl = apiBase.trim().replace(/\/$/, '')
    const modelsUrl = `${baseUrl}/models`

    const response = await fetch(modelsUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch models: ${response.status} ${response.statusText}`)
    }

    const data: ModelsResponse = await response.json()
    
    if (!data.data || !Array.isArray(data.data)) {
      throw new Error('Invalid response format')
    }

    // 提取模型ID并排序
    return data.data
      .map(model => model.id)
      .filter(id => id && id.trim())
      .sort()
  } catch (error: any) {
    console.error('Error fetching models:', error)
    throw error
  }
}

/**
 * Get default models for common providers
 */
export function getDefaultModels(apiBase: string): string[] {
  const base = apiBase.toLowerCase()
  
  // OpenAI
  if (base.includes('openai.com') || !apiBase) {
    return [
      'gpt-4o',
      'gpt-4o-mini',
      'gpt-4-turbo',
      'gpt-4',
      'gpt-3.5-turbo'
    ]
  }
  
  // Anthropic
  if (base.includes('anthropic.com')) {
    return [
      'claude-3-5-sonnet-20241022',
      'claude-3-opus-20240229',
      'claude-3-sonnet-20240229',
      'claude-3-haiku-20240307'
    ]
  }
  
  // 其他通用模型
  return [
    'gpt-4o-mini',
    'gpt-4o',
    'gpt-3.5-turbo'
  ]
}

/**
 * Model cache to avoid repeated API calls
 */
class ModelCache {
  private cache: Map<string, { models: string[], timestamp: number }> = new Map()
  private readonly TTL = 5 * 60 * 1000 // 5分钟缓存

  getCacheKey(apiBase: string, apiKey: string): string {
    // 使用API Base和API Key的前8位作为缓存键
    return `${apiBase}_${apiKey.substring(0, 8)}`
  }

  get(apiBase: string, apiKey: string): string[] | null {
    const key = this.getCacheKey(apiBase, apiKey)
    const cached = this.cache.get(key)
    
    if (!cached) return null
    
    // 检查是否过期
    if (Date.now() - cached.timestamp > this.TTL) {
      this.cache.delete(key)
      return null
    }
    
    return cached.models
  }

  set(apiBase: string, apiKey: string, models: string[]): void {
    const key = this.getCacheKey(apiBase, apiKey)
    this.cache.set(key, {
      models,
      timestamp: Date.now()
    })
  }

  clear(): void {
    this.cache.clear()
  }
}

export const modelCache = new ModelCache()

/**
 * Fetch models with caching
 */
export async function fetchModelsWithCache(apiBase: string, apiKey: string): Promise<string[]> {
  if (!apiBase || !apiKey) {
    return getDefaultModels(apiBase)
  }

  // 检查缓存
  const cached = modelCache.get(apiBase, apiKey)
  if (cached) {
    return cached
  }

  try {
    // 从API获取
    const models = await fetchModels(apiBase, apiKey)
    
    // 缓存结果
    modelCache.set(apiBase, apiKey, models)
    
    return models
  } catch (error) {
    console.warn('Failed to fetch models, using defaults:', error)
    // 失败时返回默认模型
    return getDefaultModels(apiBase)
  }
}
