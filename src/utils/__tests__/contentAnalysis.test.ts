import { describe, it, expect } from 'vitest'
import {
  clusterByTopic,
  analyzePriorityHints,
  detectDuplicatesAndNoise,
  runFullAnalysis,
  detectCategory,
  computeRelevance,
  getQualitySignals,
} from '../contentAnalysis'
import type { ContentItem } from '../../types/workflow'

describe('contentAnalysis', () => {
  const mockItems = [
    {
      _id: 1,
      title: 'OpenAI 发布 GPT-5 模型',
      content: 'OpenAI 今日发布了最新的 GPT-5 语言模型，性能大幅提升，可以处理更复杂的任务',
      source: 'TechCrunch',
      url: 'https://example.com/1',
      published: '2024-01-01',
    },
    {
      _id: 2,
      title: '谷歌推出新一代 AI 芯片',
      content: '谷歌推出第五代 TPU 芯片，专为大规模 AI 训练和推理优化',
      source: 'Bloomberg',
      url: 'https://example.com/2',
      published: '2024-01-02',
    },
    {
      _id: 3,
      title: 'OpenAI GPT-5 发布会直播',
      content: 'OpenAI 举办 GPT-5 发布会，展示了模型的强大能力',
      source: 'The Verge',
      url: 'https://example.com/3',
      published: '2024-01-01',
    },
    {
      _id: 4,
      title: '广告',
      content: '点击购买',
      source: 'Ad',
      url: 'https://example.com/ad',
      published: '2024-01-03',
    },
  ]

  describe('clusterByTopic', () => {
    it('应该将相似主题的内容聚类在一起', () => {
      const clusters = clusterByTopic(mockItems.slice(0, 3))

      expect(clusters.length).toBeGreaterThan(0)
      expect(clusters.every(c => c.itemIds.length > 0)).toBe(true)
      expect(clusters.every(c => c.name.length > 0)).toBe(true)
      expect(clusters.every(c => c.color && c.bg)).toBe(true)
    })

    it('应该为空列表返回空聚类', () => {
      const clusters = clusterByTopic([])
      expect(clusters).toEqual([])
    })

    it('应该识别 GPT-5 相关的聚类', () => {
      const clusters = clusterByTopic(mockItems.slice(0, 3))
      
      const gptCluster = clusters.find(c => 
        c.itemIds.includes(1) && c.itemIds.includes(3)
      )
      expect(gptCluster).toBeDefined()
    })

    it('聚类应该有不同的颜色', () => {
      const items = Array.from({ length: 10 }, (_, i) => ({
        _id: i,
        title: `Topic ${i}`,
        content: `Content about topic ${i} with unique keywords ${i}`,
      }))

      const clusters = clusterByTopic(items)
      const colors = new Set(clusters.map(c => c.color))
      expect(colors.size).toBeGreaterThan(1)
    })
  })

  describe('analyzePriorityHints', () => {
    it('应该为相关度高的内容分配较高优先级', () => {
      const hints = analyzePriorityHints(mockItems.slice(0, 3), 'OpenAI GPT AI')

      const hint1 = hints.get(1)

      expect(hint1).toBeDefined()
      expect(['mainline', 'expandable']).toContain(hint1?.priorityHint)
    })

    it('应该为内容丰富的条目加分', () => {
      const richItem = {
        _id: 100,
        title: '深度技术分析',
        content: '这是一篇非常详细的技术分析文章，包含了大量的技术细节、案例研究和深入的洞察。'.repeat(5),
        source: 'TechCrunch',
      }

      const shortItem = {
        _id: 101,
        title: '简短新闻',
        content: '简短内容',
        source: 'Blog',
      }

      const hints = analyzePriorityHints([richItem, shortItem])
      const richHint = hints.get(100)
      const shortHint = hints.get(101)

      expect(richHint?.priorityHint).toBe('mainline')
      expect(shortHint?.priorityHint).toBe('background')
    })

    it('应该识别可靠来源', () => {
      const reliableItem = {
        _id: 200,
        title: 'Breaking News',
        content: 'Important news from reliable source',
        source: 'Reuters',
      }

      const hints = analyzePriorityHints([reliableItem])
      const hint = hints.get(200)

      expect(hint?.priorityReason).toContain('来源可靠')
    })

    it('应该识别多源确认', () => {
      const items = [
        {
          _id: 1,
          title: 'OpenAI 发布 GPT-5',
          content: 'Content 1',
          source: 'TechCrunch',
        },
        {
          _id: 2,
          title: 'OpenAI 发布 GPT-5 模型',
          content: 'Content 2',
          source: 'The Verge',
        },
        {
          _id: 3,
          title: 'GPT-5 正式发布',
          content: 'Content 3',
          source: 'Bloomberg',
        },
      ]

      const hints = analyzePriorityHints(items)
      const hint1 = hints.get(1)

      expect(hint1?.priorityReason).toBeDefined()
    })

    it('没有用户主题时应该基于其他因素评分', () => {
      const hints = analyzePriorityHints(mockItems.slice(0, 2))
      
      expect(hints.size).toBe(2)
      expect(hints.get(1)).toBeDefined()
      expect(hints.get(2)).toBeDefined()
    })
  })

  describe('detectDuplicatesAndNoise', () => {
    it('应该识别高度相似的重复内容', () => {
      const duplicateItems = [
        {
          _id: 1,
          title: 'OpenAI 发布 GPT-5',
          content: 'OpenAI 今日发布了最新的 GPT-5 模型',
          source: 'Source A',
        },
        {
          _id: 2,
          title: 'OpenAI 发布 GPT-5',
          content: 'OpenAI 今日发布了最新的 GPT-5 模型',
          source: 'Source B',
        },
      ]

      const { duplicates } = detectDuplicatesAndNoise(duplicateItems)
      expect(duplicates.size).toBeGreaterThan(0)
      
      if (duplicates.has(2)) {
        const dup = duplicates.get(2)!
        expect(dup.duplicateOf).toBe(1)
        expect(dup.similarity).toBeGreaterThan(0.4)
      }
    })

    it('应该识别低质量噪声内容', () => {
      const { noise } = detectDuplicatesAndNoise(mockItems)

      const noiseItem = noise.get(4)
      expect(noiseItem).toBeDefined()
      expect(noiseItem?.reason).toBeDefined()
    })

    it('应该识别信息密度低的内容', () => {
      const lowDensityItem = {
        _id: 999,
        title: '短',
        content: '太短',
        source: 'Test',
      }

      const { noise } = detectDuplicatesAndNoise([lowDensityItem])
      expect(noise.has(999)).toBe(true)
      expect(noise.get(999)?.reason).toContain('信息密度')
    })

    it('应该识别缺少正文的标题', () => {
      const titleOnlyItem = {
        _id: 888,
        title: '标题很短',
        content: '',
        source: 'Test',
      }

      const { noise } = detectDuplicatesAndNoise([titleOnlyItem])
      expect(noise.has(888)).toBe(true)
      expect(noise.get(888)?.reason).toContain('缺少正文')
    })

    it('应该识别来源重复', () => {
      const items = [
        {
          _id: 1,
          title: 'News A',
          content: 'Content A',
          url: 'https://same.com/article',
          source: 'Source A',
        },
        {
          _id: 2,
          title: 'News B',
          content: 'Content B',
          url: 'https://same.com/article',
          source: 'Source B',
        },
      ]

      const { noise } = detectDuplicatesAndNoise(items)
      expect(noise.size).toBeGreaterThan(0)
    })

    it('空列表应该返回空结果', () => {
      const { duplicates, noise } = detectDuplicatesAndNoise([])
      expect(duplicates.size).toBe(0)
      expect(noise.size).toBe(0)
    })
  })

  describe('runFullAnalysis', () => {
    it('应该执行完整的分析流程', () => {
      const result = runFullAnalysis(mockItems.slice(0, 3), 'OpenAI AI')

      expect(result.clusters).toBeDefined()
      expect(result.hints).toBeDefined()
      expect(result.clusters.length).toBeGreaterThan(0)
      expect(result.hints.size).toBeGreaterThan(0)
    })

    it('应该为每个条目生成提示信息', () => {
      const result = runFullAnalysis(mockItems.slice(0, 3))

      expect(result.hints.size).toBe(3)
      
      for (const hint of result.hints.values()) {
        expect(hint).toBeDefined()
        expect(hint.priorityHint).toBeDefined()
      }
    })

    it('应该标记重复和噪声', () => {
      const result = runFullAnalysis(mockItems)

      for (const hint of result.hints.values()) {
        if (hint.isLowDensity) {
          expect(hint.noiseReason).toBeDefined()
        }
        if (hint.duplicateOf !== undefined) {
          expect(hint.duplicateScore).toBeDefined()
        }
      }
    })
  })

  describe('detectCategory', () => {
    it('应该根据关键词识别类别', () => {
      const aiItem: ContentItem = {
        title: 'AI 突破性进展',
        content: '人工智能技术取得重大突破',
        source: 'Test',
      }

      const category = detectCategory(aiItem)
      expect(category).toBeDefined()
      expect(category?.id).toBeDefined()
    })

    it('无法识别时应该返回 null', () => {
      const randomItem: ContentItem = {
        title: 'Random Title',
        content: 'Random content without keywords',
        source: 'Test',
      }

      const category = detectCategory(randomItem)
      expect(category).toBeNull()
    })
  })

  describe('computeRelevance', () => {
    it('应该计算内容与主题的相关度', () => {
      const item: ContentItem = {
        title: 'OpenAI 发布 GPT-5',
        content: 'AI 模型技术突破',
        source: 'Test',
      }

      const highRelevance = computeRelevance(item, 'OpenAI GPT AI')
      const lowRelevance = computeRelevance(item, '区块链 加密货币')

      expect(highRelevance).toBe('high')
      expect(lowRelevance).toBe('low')
    })

    it('没有主题时应该返回 medium', () => {
      const item: ContentItem = { title: 'Test', content: 'Test', source: 'Test' }
      expect(computeRelevance(item, '')).toBe('medium')
    })
  })

  describe('getQualitySignals', () => {
    it('应该识别多来源确认信号', () => {
      const items: ContentItem[] = [
        { title: 'OpenAI 发布 GPT-5', content: 'Content 1', source: 'A' },
        { title: 'OpenAI 发布 GPT-5 模型', content: 'Content 2', source: 'B' },
      ]

      const signals = getQualitySignals(items[0], items)
      expect(signals.some(s => s.text.includes('多来源'))).toBe(true)
    })

    it('应该识别可靠来源信号', () => {
      const item: ContentItem = {
        title: 'Breaking News',
        content: 'Important update',
        source: 'Reuters',
      }

      const signals = getQualitySignals(item, [item])
      expect(signals.some(s => s.text.includes('可靠来源'))).toBe(true)
    })

    it('应该识别主题相关信号', () => {
      const item: ContentItem = {
        title: 'AI 技术进展',
        content: '人工智能领域的最新发展',
        source: 'Tech Blog',
      }

      const signals = getQualitySignals(item, [item], 'AI 人工智能')
      expect(signals.some(s => s.text.includes('关注'))).toBe(true)
    })

    it('应该限制返回最多2个信号', () => {
      const item: ContentItem = {
        title: 'OpenAI AI 突破',
        content: '重大技术突破',
        source: 'Reuters',
      }

      const items = [
        item,
        { title: 'OpenAI 相关', content: 'Related', source: 'B' },
      ]

      const signals = getQualitySignals(item, items, 'OpenAI AI')
      expect(signals.length).toBeLessThanOrEqual(2)
    })
  })
})
