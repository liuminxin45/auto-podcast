import type { Priority } from '../constants/priorities'
import type { ContentItem } from './workflow'

export type ViewMode = 'quick' | 'detailed'

export interface OrganizeItem extends ContentItem {
  _source_channel?: 'auto' | 'manual'
  _id: number
}

export interface CandidateItem extends OrganizeItem {
  _priority: Priority
  _order: number
}
