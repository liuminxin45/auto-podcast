import type { IdeationResult, IdeationContext, IdeationConfig } from '../../types/ideation'

export interface IdeationHistoryRecord {
  id: string
  timestamp: string
  
  // 输入上下文
  input: {
    materials: Array<{
      id: string
      title: string
      source?: string
    }>
    materialCount: number
    config: IdeationConfig
    context: Partial<IdeationContext>
  }
  
  // 输出结果
  output: IdeationResult | null
  
  // 状态
  success: boolean
  error?: string
  warnings?: string[]
}

const STORAGE_KEY = 'auto-podcast.ideation.history.v1'
const MAX_RECORDS = 50

class IdeationHistoryService {
  private getRecords(): IdeationHistoryRecord[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      if (!data) return []
      return JSON.parse(data)
    } catch (error) {
      console.error('[IdeationHistory] Failed to load records:', error)
      return []
    }
  }

  private saveRecords(records: IdeationHistoryRecord[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records))
    } catch (error) {
      console.error('[IdeationHistory] Failed to save records:', error)
    }
  }

  save(
    context: IdeationContext,
    config: IdeationConfig,
    result: IdeationResult | null,
    success: boolean,
    error?: string,
    warnings?: string[]
  ): string {
    const record: IdeationHistoryRecord = {
      id: `history_${Date.now()}`,
      timestamp: new Date().toISOString(),
      input: {
        materials: context.materials.map((m, idx) => ({
          id: m.url || `material_${idx}`,
          title: m.title || '无标题',
          source: m.source,
        })),
        materialCount: context.materials.length,
        config,
        context: {
          user_preferences: context.user_preferences,
          ideation_challenge: context.ideation_challenge,
          target_topic: context.target_topic,
        },
      },
      output: result,
      success,
      error,
      warnings,
    }

    let records = this.getRecords()
    records.unshift(record)
    
    if (records.length > MAX_RECORDS) {
      records = records.slice(0, MAX_RECORDS)
    }
    
    this.saveRecords(records)
    return record.id
  }

  getAll(): IdeationHistoryRecord[] {
    return this.getRecords()
  }

  getById(id: string): IdeationHistoryRecord | null {
    const records = this.getRecords()
    return records.find(r => r.id === id) || null
  }

  delete(id: string): boolean {
    const records = this.getRecords()
    const filtered = records.filter(r => r.id !== id)
    
    if (filtered.length === records.length) {
      return false
    }
    
    this.saveRecords(filtered)
    return true
  }

  clear(): void {
    localStorage.removeItem(STORAGE_KEY)
  }

  getStats(): { total: number; successful: number; failed: number } {
    const records = this.getRecords()
    return {
      total: records.length,
      successful: records.filter(r => r.success).length,
      failed: records.filter(r => !r.success).length,
    }
  }
}

export const ideationHistoryService = new IdeationHistoryService()
