import type { ContentItem } from '../types/workflow'
import { llmService } from './llmService'
import { LLMError } from '../types/llm'
import { delay } from './llm/utils'
import { isDebugModeEnabled } from '../utils/debugMode'
import { LLM_DEFAULTS } from '../constants/llm'
import { CLUSTER_COLORS } from '../constants/colors'

export interface OrganizeConfig {
  userInstruction?: string
  strictness: 'loose' | 'medium' | 'strict'
  apiBase: string
  apiKey: string
  model: string
}

export interface OrganizeResult {
  processed: ContentItem[]
  clusters: ClusterInfo[]
  stats: {
    total: number
    selected: number
    rejected: number
    noise: number
    duplicate: number
  }
  logs: string[]
}

export interface OrganizeProgress {
  step: 'denoise' | 'cluster' | 'select'
  stepLabel: string
  progress: number
  currentBatch?: number
  totalBatches?: number
  message: string
}

export interface ClusterInfo {
  id: string
  name: string
  description: string
  items: ContentItem[]
  color: string
}

export class OrganizeAIService {
  private config: OrganizeConfig
  private logs: string[] = []
  private onProgress?: (progress: OrganizeProgress) => void

  constructor(config: OrganizeConfig, onProgress?: (progress: OrganizeProgress) => void) {
    this.config = config
    this.onProgress = onProgress
  }

  private reportProgress(progress: OrganizeProgress) {
    if (this.onProgress) {
      this.onProgress(progress)
    }
  }

  async runFullOrganize(items: ContentItem[]): Promise<OrganizeResult> {
    this.logs = []
    this.log(`开始 AI 整理，共 ${items.length} 条素材`)

    this.reportProgress({
      step: 'denoise',
      stepLabel: 'Step 1: 去噪与去重',
      progress: 0,
      message: '正在准备...',
    })

    const step1 = await this.step1_denoise(items)
    this.log(`去噪完成：保留 ${step1.kept.length}，移除 ${step1.removed.length}`)

    this.reportProgress({
      step: 'cluster',
      stepLabel: 'Step 2: 话题聚类',
      progress: 33,
      message: '正在分析话题...',
    })

    const step2 = await this.step2_cluster(step1.kept)
    this.log(`聚类完成：发现 ${step2.length} 个话题簇`)

    this.reportProgress({
      step: 'select',
      stepLabel: 'Step 3: 智能筛选',
      progress: 66,
      message: '正在评分筛选...',
    })

    const step3 = await this.step3_select(step2)
    this.log(`筛选完成：选入 ${step3.selected.length}，拒绝 ${step3.rejected.length}`)

    const processed = [...step3.selected, ...step3.rejected, ...step1.removed]

    const stats = {
      total: items.length,
      selected: processed.filter(i => i._ai_organize?.status === 'selected').length,
      rejected: processed.filter(i => i._ai_organize?.status === 'rejected').length,
      noise: processed.filter(i => i._ai_organize?.status === 'noise').length,
      duplicate: processed.filter(i => i._ai_organize?.status === 'duplicate').length,
    }

    return {
      processed,
      clusters: step2,
      stats,
      logs: this.logs,
    }
  }

  private log(msg: string) {
    this.logs.push(msg)
  }

  private async step1_denoise(items: ContentItem[]): Promise<{ kept: ContentItem[]; removed: ContentItem[] }> {
    this.log('Step 1: 去噪与去重...')

    const batchSize = LLM_DEFAULTS.BATCH_SIZE
    const allResults: ContentItem[] = []
    const totalBatches = Math.ceil(items.length / batchSize)

    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize)
      const currentBatch = Math.floor(i / batchSize) + 1
      
      this.reportProgress({
        step: 'denoise',
        stepLabel: 'Step 1: 去噪与去重',
        progress: Math.round((i / items.length) * 33),
        currentBatch,
        totalBatches,
        message: `正在处理第 ${currentBatch}/${totalBatches} 批...`,
      })
      
      this.log(`处理第 ${currentBatch}/${totalBatches} 批`)

      const prompt = this.buildDenoisePrompt(batch)
      const response = await this.callLLM(prompt)
      const parsed = this.parseJSONResponse(response)

      batch.forEach((item, idx) => {
        const result = parsed[idx] || { status: 'keep', reason: '默认保留' }
        allResults.push({
          ...item,
          _ai_organize: {
            status: result.status === 'drop' ? 'noise' : result.status === 'duplicate' ? 'duplicate' : 'selected',
            reason: result.reason || '',
            confidence: result.confidence || 0.5,
            duplicate_of: result.duplicate_of,
          },
        })
      })

      await delay(LLM_DEFAULTS.BATCH_DELAY)
    }

    const kept = allResults.filter(i => i._ai_organize?.status === 'selected')
    const removed = allResults.filter(i => i._ai_organize?.status !== 'selected')

    return { kept, removed }
  }

  private async step2_cluster(items: ContentItem[]): Promise<ClusterInfo[]> {
    this.log('Step 2: 话题聚类...')

    if (items.length === 0) return []

    const prompt = this.buildClusterPrompt(items)
    const response = await this.callLLM(prompt)
    const parsed = this.parseJSONResponse(response)

    const clusters: ClusterInfo[] = []

    if (Array.isArray(parsed.clusters)) {
      parsed.clusters.forEach((c: any, idx: number) => {
        const clusterId = `cluster_${idx}`
        clusters.push({
          id: clusterId,
          name: c.name || `话题 ${idx + 1}`,
          description: c.description || '',
          items: [],
          color: CLUSTER_COLORS[idx % CLUSTER_COLORS.length].color,
        })
      })
    }

    if (Array.isArray(parsed.assignments)) {
      parsed.assignments.forEach((assignment: any, idx: number) => {
        const item = items[idx]
        if (!item) return

        const clusterId = `cluster_${assignment.cluster_index || 0}`
        const cluster = clusters.find(c => c.id === clusterId)

        if (cluster) {
          cluster.items.push({
            ...item,
            _ai_organize: {
              ...item._ai_organize,
              cluster_id: clusterId,
              cluster_name: cluster.name,
              tags: assignment.tags || [],
            } as any,
          })
        }
      })
    }

    return clusters.filter(c => c.items.length > 0)
  }

  private async step3_select(clusters: ClusterInfo[]): Promise<{ selected: ContentItem[]; rejected: ContentItem[] }> {
    this.log('Step 3: 最终筛选与评分...')

    const allItems = clusters.flatMap(c => c.items)
    if (allItems.length === 0) return { selected: [], rejected: [] }

    const debugMode = isDebugModeEnabled()
    
    if (debugMode) {
      this.log('⚡ Debug mode: 跳过 AI 评分，使用固定分数')
      const scoredItems = allItems.map(item => ({
        ...item,
        _ai_organize: {
          ...item._ai_organize,
          status: 'selected',
          score: 60,
          reason: '调试模式固定分',
          confidence: 1,
        } as any,
      }))
      return { selected: scoredItems, rejected: [] }
    }

    const strictnessThreshold = {
      loose: 30,
      medium: 50,
      strict: 70,
    }[this.config.strictness]

    const batchSize = LLM_DEFAULTS.BATCH_SIZE
    const scoredItems: ContentItem[] = []
    const totalBatches = Math.ceil(allItems.length / batchSize)

    for (let i = 0; i < allItems.length; i += batchSize) {
      const batch = allItems.slice(i, i + batchSize)
      const currentBatch = Math.floor(i / batchSize) + 1
      
      this.reportProgress({
        step: 'select',
        stepLabel: 'Step 3: 智能筛选',
        progress: 66 + Math.round((i / allItems.length) * 33),
        currentBatch,
        totalBatches,
        message: `正在评分第 ${currentBatch}/${totalBatches} 批...`,
      })
      
      this.log(`评分第 ${currentBatch}/${totalBatches} 批`)

      const prompt = this.buildScoringPrompt(batch)
      const response = await this.callLLM(prompt)
      const parsed = this.parseJSONResponse(response)

      batch.forEach((item, idx) => {
        const result = parsed[idx] || { score: 50, reason: '默认评分' }
        const score = result.score || 50
        const decision = score >= strictnessThreshold ? 'selected' : 'rejected'

        scoredItems.push({
          ...item,
          _ai_organize: {
            ...item._ai_organize,
            status: decision,
            score,
            reason: result.reason || item._ai_organize?.reason || '',
            confidence: result.confidence || item._ai_organize?.confidence || 0.5,
          } as any,
        })
      })

      await delay(LLM_DEFAULTS.BATCH_DELAY)
    }

    scoredItems.sort((a, b) => (b._ai_organize?.score || 0) - (a._ai_organize?.score || 0))

    const selected = scoredItems.filter(i => i._ai_organize?.status === 'selected')
    const rejected = scoredItems.filter(i => i._ai_organize?.status === 'rejected')

    return { selected, rejected }
  }

  private buildDenoisePrompt(batch: ContentItem[]): string {
    return `你是专业的内容主编。请分析以下内容，识别低质量、重复或无关的条目。

内容列表：
${batch.map((item, idx) => `${idx}. 标题：${item.title || '无标题'}\n   内容：${(item.content || '').slice(0, 150)}\n   来源：${item.source || '未知'}`).join('\n\n')}

请为每条内容输出 JSON 数组，格式：
[
  {
    "index": 0,
    "status": "keep" | "drop" | "duplicate",
    "reason": "一句话说明理由",
    "confidence": 0-1,
    "duplicate_of": 可选，如果是重复则标注原始条目索引
  }
]

识别规则：
- drop: 广告、软文、无意义短句、质量极低
- duplicate: 与其他条目高度重复
- keep: 保留

只输出 JSON 数组，不要其他内容。`
  }

  private buildClusterPrompt(items: ContentItem[]): string {
    const userHint = this.config.userInstruction
      ? `\n用户关注方向：${this.config.userInstruction}`
      : ''

    return `你是专业的内容主编。请将以下内容按话题聚类。${userHint}

内容列表：
${items.map((item, idx) => `${idx}. ${item.title || '无标题'}\n   ${(item.content || '').slice(0, 100)}`).join('\n\n')}

请输出 JSON 格式：
{
  "clusters": [
    {
      "name": "话题名称",
      "description": "一句话描述"
    }
  ],
  "assignments": [
    {
      "cluster_index": 0,
      "tags": ["标签1", "标签2"]
    }
  ]
}

assignments 数组长度必须等于内容数量，按索引对应。
只输出 JSON，不要其他内容。`
  }

  private buildScoringPrompt(batch: ContentItem[]): string {
    const userHint = this.config.userInstruction
      ? `\n用户指令：${this.config.userInstruction}`
      : ''

    return `你是专业的内容主编。请为以下内容评分（0-100）。${userHint}

评分标准：
- 80-100: 核心素材，必选
- 60-79: 有价值，推荐
- 40-59: 可选，视情况
- 0-39: 不推荐

内容列表：
${batch.map((item, idx) => {
  const cluster = item._ai_organize?.cluster_name ? ` [${item._ai_organize.cluster_name}]` : ''
  return `${idx}. ${item.title || '无标题'}${cluster}\n   ${(item.content || '').slice(0, 120)}`
}).join('\n\n')}

请输出 JSON 数组：
[
  {
    "index": 0,
    "score": 0-100,
    "reason": "一句话评价",
    "confidence": 0-1
  }
]

只输出 JSON 数组，不要其他内容。`
  }

  private async callLLM(prompt: string): Promise<string> {
    try {
      const response = await llmService.call({
        apiBase: this.config.apiBase,
        apiKey: this.config.apiKey,
        model: this.config.model,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.3,
      })

      return response.choices[0].message.content
    } catch (error: any) {
      if (error instanceof LLMError) {
        throw new Error(`LLM 调用失败: ${error.message}`)
      }
      throw error
    }
  }

  private parseJSONResponse(content: string): any {
    let cleaned = content.trim()

    if (cleaned.includes('```json')) {
      cleaned = cleaned.split('```json')[1].split('```')[0].trim()
    } else if (cleaned.includes('```')) {
      cleaned = cleaned.split('```')[1].split('```')[0].trim()
    }

    try {
      return JSON.parse(cleaned)
    } catch (e) {
      console.error('JSON parse error:', e, 'Content:', cleaned.slice(0, 200))
      return []
    }
  }
}
