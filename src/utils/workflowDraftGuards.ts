import type { StructureBlock } from '../types/ideation'
import type { CandidateItem, ViewMode } from '../types/organize'

export function isViewMode(value: unknown): value is ViewMode {
  return value === 'quick' || value === 'detailed'
}

function isCandidateItem(value: unknown): value is CandidateItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<CandidateItem>
  return typeof item._id === 'number'
    && typeof item._order === 'number'
    && (item._priority === 'primary' || item._priority === 'important' || item._priority === 'backup')
}

export function toCandidateItems(value: unknown): CandidateItem[] {
  return Array.isArray(value) ? value.filter(isCandidateItem) : []
}

export function toNumberArray(value: unknown): number[] {
  return Array.isArray(value) ? value.filter((item): item is number => typeof item === 'number') : []
}

export function toStructureBlocks(value: unknown): StructureBlock[] {
  return Array.isArray(value) ? value.filter((item): item is StructureBlock => {
    if (!item || typeof item !== 'object') return false
    const block = item as Partial<StructureBlock>
    return typeof block.id === 'string'
      && typeof block.type === 'string'
      && Array.isArray(block.materials)
  }) : []
}
