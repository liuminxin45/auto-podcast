import type { ContentCreationType } from '../types/workflow'

export const CONTENT_TYPE_META: Record<ContentCreationType, { label: string; icon: string; desc: string }> = {
  story: { label: '故事型', icon: '📖', desc: '围绕核心主线展开，兼顾背景与延伸讨论' },
  news_brief: { label: '新闻早报', icon: '🗞️', desc: '开场导语 + 多条新闻播报 + 结尾总结' },
}
