import type { CSSProperties, ReactNode } from 'react'

type Tone = 'default' | 'success' | 'warning' | 'error' | 'info'

const toneClass: Record<Tone, string> = {
  default: 'ui-tone-default',
  success: 'ui-tone-success',
  warning: 'ui-tone-warning',
  error: 'ui-tone-error',
  info: 'ui-tone-info',
}

export function PanelSurface({
  children,
  className = '',
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <section className={`ui-surface ${className}`} style={style}>
      {children}
    </section>
  )
}

export function SectionHeader({
  title,
  desc,
  action,
}: {
  title: ReactNode
  desc?: ReactNode
  action?: ReactNode
}) {
  return (
    <header className="ui-section-header">
      <div>
        <div className="ui-section-title">{title}</div>
        {desc && <div className="ui-section-desc">{desc}</div>}
      </div>
      {action && <div className="ui-section-action">{action}</div>}
    </header>
  )
}

export function StatusBadge({
  children,
  tone = 'default',
}: {
  children: ReactNode
  tone?: Tone
}) {
  return <span className={`ui-status-badge ${toneClass[tone]}`}>{children}</span>
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="ui-toolbar">{children}</div>
}

export function EmptyState({
  title,
  desc,
}: {
  title: ReactNode
  desc?: ReactNode
}) {
  return (
    <div className="ui-empty-state">
      <div className="ui-empty-title">{title}</div>
      {desc && <div className="ui-empty-desc">{desc}</div>}
    </div>
  )
}

export function MetricCell({
  label,
  value,
  tone = 'default',
}: {
  label: ReactNode
  value: ReactNode
  tone?: Tone
}) {
  return (
    <div className={`ui-metric-cell ${toneClass[tone]}`}>
      <div className="ui-metric-value">{value}</div>
      <div className="ui-metric-label">{label}</div>
    </div>
  )
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: Array<{ value: T; label: ReactNode }>
  onChange: (value: T) => void
}) {
  return (
    <div className="ui-segmented-control">
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? 'is-active' : ''}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

