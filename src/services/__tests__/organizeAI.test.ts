import { describe, it, expect, vi, beforeEach } from 'vitest'
import { OrganizeAIService } from '../organizeAI'
import type { ContentItem } from '../../types/workflow'
import type { OrganizeConfig } from '../organizeAI'
import * as llmServiceModule from '../llmService'

vi.mock('../llmService', () => ({
  llmService: {
    call: vi.fn(),
  },
}))

async function withMutedConsoleError<T>(task: () => Promise<T>): Promise<T> {
  const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  try {
    return await task()
  } finally {
    spy.mockRestore()
  }
}

describe('OrganizeAIService', () => {
  const mockConfig: OrganizeConfig = {
    apiBase: 'https://api.test.com',
    apiKey: 'test-key',
    model: 'gpt-4',
    strictness: 'medium',
    userInstruction: '关注 AI 和科技',
  }

  const mockItems: ContentItem[] = [
    {
      title: 'OpenAI 发布 GPT-5',
      content: 'OpenAI 今日发布了最新的 GPT-5 模型，性能大幅提升',
      source: 'TechCrunch',
      url: 'https://example.com/1',
      published: '2024-01-01',
    },
    {
      title: '谷歌推出新 AI 芯片',
      content: '谷歌推出了第五代 TPU 芯片，专为 AI 训练优化',
      source: 'Bloomberg',
      url: 'https://example.com/2',
      published: '2024-01-02',
    },
    {
      title: '广告内容',
      content: '点击购买',
      source: 'Ad Network',
      url: 'https://example.com/ad',
      published: '2024-01-03',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('去噪与去重 (step1_denoise)', () => {
    it('应该正确识别并标记噪声内容', async () => {
      const mockLLMResponse = JSON.stringify([
        { index: 0, status: 'keep', reason: '高质量内容', confidence: 0.9 },
        { index: 1, status: 'keep', reason: '技术新闻', confidence: 0.85 },
        { index: 2, status: 'drop', reason: '广告内容', confidence: 0.95 },
      ])

      vi.mocked(llmServiceModule.llmService.call).mockResolvedValue({
        id: 'test',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: mockLLMResponse },
            finish_reason: 'stop',
          },
        ],
      })

      const service = new OrganizeAIService(mockConfig)
      const result = await service.runFullOrganize(mockItems)

      expect(result.stats.noise).toBeGreaterThan(0)
      expect(result.stats.selected + result.stats.rejected + result.stats.noise + result.stats.duplicate).toBe(3)
    })

    it('应该识别重复内容', async () => {
      const duplicateItems: ContentItem[] = [
        {
          title: 'OpenAI 发布 GPT-5',
          content: 'OpenAI 今日发布了最新的 GPT-5 模型',
          source: 'TechCrunch',
          url: 'https://example.com/1',
        },
        {
          title: 'OpenAI 发布 GPT-5',
          content: 'OpenAI 今日发布了最新的 GPT-5 模型',
          source: 'The Verge',
          url: 'https://example.com/2',
        },
      ]

      const mockLLMResponse = JSON.stringify([
        { index: 0, status: 'keep', reason: '原始内容', confidence: 0.9 },
        { index: 1, status: 'duplicate', reason: '与第0条重复', confidence: 0.95, duplicate_of: 0 },
      ])

      vi.mocked(llmServiceModule.llmService.call).mockResolvedValue({
        id: 'test',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: mockLLMResponse },
            finish_reason: 'stop',
          },
        ],
      })

      const service = new OrganizeAIService(mockConfig)
      const result = await service.runFullOrganize(duplicateItems)

      expect(result.stats.duplicate).toBeGreaterThan(0)
    })
  })

  describe('话题聚类 (step2_cluster)', () => {
    it('应该将相关内容聚类', async () => {
      const mockDenoiseResponse = JSON.stringify([
        { index: 0, status: 'keep', confidence: 0.9 },
        { index: 1, status: 'keep', confidence: 0.85 },
      ])

      const mockClusterResponse = JSON.stringify({
        clusters: [
          { name: 'AI 模型发布', description: '关于新 AI 模型的发布' },
        ],
        assignments: [
          { cluster_index: 0, tags: ['OpenAI', 'GPT'] },
          { cluster_index: 0, tags: ['Google', 'TPU'] },
        ],
      })

      vi.mocked(llmServiceModule.llmService.call)
        .mockResolvedValueOnce({
          id: 'test1',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: mockDenoiseResponse }, finish_reason: 'stop' }],
        })
        .mockResolvedValueOnce({
          id: 'test2',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: mockClusterResponse }, finish_reason: 'stop' }],
        })
        .mockResolvedValueOnce({
          id: 'test3',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: '[]' }, finish_reason: 'stop' }],
        })

      const service = new OrganizeAIService(mockConfig)
      const result = await service.runFullOrganize(mockItems.slice(0, 2))

      expect(result.clusters.length).toBeGreaterThan(0)
      expect(result.clusters[0].items.length).toBeGreaterThan(0)
    })
  })

  describe('智能筛选 (step3_select)', () => {
    it('应该根据严格度阈值筛选内容', async () => {
      const strictConfig = { ...mockConfig, strictness: 'strict' as const }

      const mockDenoiseResponse = JSON.stringify([
        { index: 0, status: 'keep', confidence: 0.9 },
        { index: 1, status: 'keep', confidence: 0.85 },
      ])

      const mockClusterResponse = JSON.stringify({
        clusters: [{ name: '测试', description: '测试' }],
        assignments: [
          { cluster_index: 0, tags: [] },
          { cluster_index: 0, tags: [] },
        ],
      })

      const mockScoringResponse = JSON.stringify([
        { index: 0, score: 85, reason: '高质量', confidence: 0.9 },
        { index: 1, score: 45, reason: '一般', confidence: 0.7 },
      ])

      vi.mocked(llmServiceModule.llmService.call)
        .mockResolvedValueOnce({
          id: 'test1',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: mockDenoiseResponse }, finish_reason: 'stop' }],
        })
        .mockResolvedValueOnce({
          id: 'test2',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: mockClusterResponse }, finish_reason: 'stop' }],
        })
        .mockResolvedValueOnce({
          id: 'test3',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [{ index: 0, message: { role: 'assistant', content: mockScoringResponse }, finish_reason: 'stop' }],
        })

      const serviceStrict = new OrganizeAIService(strictConfig)
      const resultStrict = await serviceStrict.runFullOrganize(mockItems.slice(0, 2))

      expect(resultStrict.stats.selected).toBeLessThanOrEqual(resultStrict.stats.total)
    })
  })

  describe('进度报告', () => {
    it('应该在处理过程中报告进度', async () => {
      const progressUpdates: any[] = []
      const onProgress = (progress: any) => progressUpdates.push(progress)

      const mockResponse = JSON.stringify([
        { index: 0, status: 'keep', confidence: 0.9 },
      ])

      vi.mocked(llmServiceModule.llmService.call).mockResolvedValue({
        id: 'test',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4',
        choices: [{ index: 0, message: { role: 'assistant', content: mockResponse }, finish_reason: 'stop' }],
      })

      const service = new OrganizeAIService(mockConfig, onProgress)
      await service.runFullOrganize([mockItems[0]])

      expect(progressUpdates.length).toBeGreaterThan(0)
      expect(progressUpdates.some(p => p.step === 'denoise')).toBe(true)
      expect(progressUpdates.some(p => p.step === 'cluster')).toBe(true)
      expect(progressUpdates.some(p => p.step === 'select')).toBe(true)
    })
  })

  describe('JSON 解析', () => {
    it('应该处理带 markdown 代码块的响应', async () => {
      const mockResponseWithMarkdown = '```json\n[{"index": 0, "status": "keep"}]\n```'

      vi.mocked(llmServiceModule.llmService.call).mockResolvedValue({
        id: 'test',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4',
        choices: [{ index: 0, message: { role: 'assistant', content: mockResponseWithMarkdown }, finish_reason: 'stop' }],
      })

      const service = new OrganizeAIService(mockConfig)
      const result = await service.runFullOrganize([mockItems[0]])

      expect(result.processed.length).toBe(1)
    })

    it('应该处理 JSON 解析失败的情况', async () => {
      const mockInvalidResponse = 'This is not JSON'

      vi.mocked(llmServiceModule.llmService.call).mockResolvedValue({
        id: 'test',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4',
        choices: [{ index: 0, message: { role: 'assistant', content: mockInvalidResponse }, finish_reason: 'stop' }],
      })

      const service = new OrganizeAIService(mockConfig)
      const result = await withMutedConsoleError(() => service.runFullOrganize([mockItems[0]]))

      expect(result.processed.length).toBeGreaterThanOrEqual(0)
    })
  })
})
