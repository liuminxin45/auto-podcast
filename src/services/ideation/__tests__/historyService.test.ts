import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { ideationHistoryService } from '../historyService'
import type { IdeationContext, IdeationConfig, IdeationResult } from '../../../types/ideation'

const mockContext: IdeationContext = {
  materials: [
    { title: '测试素材1', content: '内容1', url: 'https://test1.com' },
    { title: '测试素材2', content: '内容2', url: 'https://test2.com' }
  ],
  user_preferences: { tone_style: 'balanced' },
  ideation_challenge: 'normal'
}

const mockConfig: IdeationConfig = {
  mode: 'hybrid',
  prefer_llm: false,
  auto_detect_type: true,
  news_auto_count: true,
  news_max_count: 8,
  news_strategy: 'coverage',
  min_quality_score: 60,
  enable_fact_check: true
}

const mockResult: IdeationResult = {
  id: 'test_ideation_1',
  timestamp: new Date().toISOString(),
  mode: 'llm',
  content_type: 'story',
  topic: {
    title: '测试主题',
    description: '测试描述'
  },
  blocks: [
    {
      id: 'block_1',
      type: 'opening',
      title: '开场',
      materials: [],
      notes: '',
      llm_generated: true
    }
  ]
}

describe('IdeationHistoryService', () => {
  beforeEach(() => {
    ideationHistoryService.clear()
  })

  afterEach(() => {
    ideationHistoryService.clear()
  })

  it('should save a successful record', () => {
    const id = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    expect(id).toBeTruthy()
    expect(id).toMatch(/^history_\d+$/)
    
    const records = ideationHistoryService.getAll()
    expect(records).toHaveLength(1)
    expect(records[0].success).toBe(true)
    expect(records[0].output).toEqual(mockResult)
  })

  it('should save a failed record with error', () => {
    const errorMsg = 'LLM调用失败'
    const id = ideationHistoryService.save(mockContext, mockConfig, null, false, errorMsg)
    
    const record = ideationHistoryService.getById(id)
    expect(record).toBeTruthy()
    expect(record!.success).toBe(false)
    expect(record!.error).toBe(errorMsg)
    expect(record!.output).toBeNull()
  })

  it('should retrieve record by id', () => {
    const id = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    const record = ideationHistoryService.getById(id)
    expect(record).toBeTruthy()
    expect(record!.id).toBe(id)
  })

  it('should return null for non-existent id', () => {
    const record = ideationHistoryService.getById('non_existent_id')
    expect(record).toBeNull()
  })

  it('should delete a record', () => {
    const id = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    const deleted = ideationHistoryService.delete(id)
    expect(deleted).toBe(true)
    
    const records = ideationHistoryService.getAll()
    expect(records).toHaveLength(0)
  })

  it('should return false when deleting non-existent record', () => {
    const deleted = ideationHistoryService.delete('non_existent_id')
    expect(deleted).toBe(false)
  })

  it('should maintain order (newest first)', () => {
    const id1 = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    const id2 = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    const records = ideationHistoryService.getAll()
    expect(records).toHaveLength(2)
    expect(records[0].id).toBe(id2)
    expect(records[1].id).toBe(id1)
  })

  it('should limit records to MAX_RECORDS', () => {
    for (let i = 0; i < 60; i++) {
      ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    }
    
    const records = ideationHistoryService.getAll()
    expect(records.length).toBeLessThanOrEqual(50)
  })

  it('should clear all records', () => {
    ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    ideationHistoryService.clear()
    
    const records = ideationHistoryService.getAll()
    expect(records).toHaveLength(0)
  })

  it('should return correct statistics', () => {
    ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    ideationHistoryService.save(mockContext, mockConfig, null, false, 'Error')
    
    const stats = ideationHistoryService.getStats()
    expect(stats.total).toBe(3)
    expect(stats.successful).toBe(2)
    expect(stats.failed).toBe(1)
  })

  it('should save with warnings', () => {
    const warnings = ['警告1', '警告2']
    const id = ideationHistoryService.save(mockContext, mockConfig, mockResult, true, undefined, warnings)
    
    const record = ideationHistoryService.getById(id)
    expect(record!.warnings).toEqual(warnings)
  })

  it('should store material info correctly', () => {
    const id = ideationHistoryService.save(mockContext, mockConfig, mockResult, true)
    
    const record = ideationHistoryService.getById(id)
    expect(record!.input.materialCount).toBe(2)
    expect(record!.input.materials).toHaveLength(2)
    expect(record!.input.materials[0].title).toBe('测试素材1')
  })
})
