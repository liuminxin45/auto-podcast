import type { ContentItem } from './workflow'

export type TrendRadarSourceKind = 'platform' | 'rss'
export type TrendRadarFilterMethod = 'keyword' | 'ai'

export interface TrendRadarSource {
  id: string
  name: string
  kind: TrendRadarSourceKind
  enabled: boolean
  url?: string
  description?: string
}

export interface TrendRadarConfigView {
  platforms_enabled: boolean
  rss_enabled: boolean
  enabled_platforms: string[]
  enabled_rss_feeds: string[]
  max_items_per_source: number
  freshness_days: number
  filter_method: TrendRadarFilterMethod
  ai_available: boolean
  ai_model?: string
  api_url?: string
  proxy_enabled: boolean
  proxy_url?: string
  schedule_preset?: string
  report_mode?: string
  raw?: Record<string, any>
}

export interface TrendRadarItem extends ContentItem {
  trendradar_id: string
  source_kind: TrendRadarSourceKind
  source_id: string
  source_name: string
  rank?: number
  score?: number
  first_seen?: string
  last_seen?: string
  report_path?: string
  matched_reason?: string
}

export interface TrendRadarMeta {
  generated_at?: string
  report_path?: string
  failed_sources?: string[]
  platform_count?: number
  rss_count?: number
  item_count?: number
  topics?: Array<{ name: string; count: number }>
  config?: Partial<TrendRadarConfigView>
}

export interface TrendRadarStatus {
  available: boolean
  adapterAvailable?: boolean
  fullRuntimeAvailable?: boolean
  runtimeBlocked?: boolean
  runtimeBlocker?: string
  processRunning: boolean
  pid?: number | null
  status: string
  localVersion?: string
  lockedVersion?: string
  lockedCommit?: string
  pythonRequirement?: string
  pythonCompatible?: boolean
  missingDependencies?: string[]
  pythonVersion?: string
  pythonExecutable?: string
  userDataDir?: string
  latestRunAt?: string | null
  latestItemCount?: number
  lastError?: string | null
}

export interface TrendRadarRunResult {
  success: boolean
  running?: boolean
  items: TrendRadarItem[]
  fetch_contents: TrendRadarItem[]
  meta: TrendRadarMeta
  error?: string
}

export interface TrendRadarUpdateStatus {
  success: boolean
  localVersion?: string
  remoteVersion?: string
  lockedVersion?: string
  localCommit?: string
  lockedCommit?: string
  remoteConfigVersions?: Record<string, string>
  pythonVersion?: string
  pythonRequirement?: string
  pythonCompatible?: boolean
  missingDependencies?: string[]
  fullRuntimeAvailable?: boolean
  remotePythonRequirement?: string
  updateAvailable: boolean
  blocked?: boolean
  blocker?: string
  error?: string
}
