export interface PlatformStatus {
  id: string
  name: string
  icon: string
  status: 'success' | 'processing' | 'failed' | 'unconfigured'
  url?: string
}

export interface AgentSuggestion {
  id: string
  title: string
  description: string
  before?: string
  after?: string
}

export interface PublishRecord {
  id: string
  title: string
  publishedAt: string
  method: 'smart' | 'quick'
  suggestionsAccepted: number
  suggestionsTotal: number
  platforms: PlatformStatus[]
}

export const DEFAULT_PLATFORMS: PlatformStatus[] = [
  { id: 'apple', name: 'Apple Podcasts', icon: '🍎', status: 'unconfigured' },
  { id: 'spotify', name: 'Spotify', icon: '💚', status: 'unconfigured' },
  { id: 'xiaoyuzhou', name: '小宇宙', icon: '🪐', status: 'unconfigured' },
  { id: 'ximalaya', name: '喜马拉雅', icon: '🏔️', status: 'unconfigured' },
]
