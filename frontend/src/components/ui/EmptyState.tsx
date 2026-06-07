import type { ReactNode } from 'react'

export interface EmptyStateProps {
  /** Emoji or small icon node shown above the title. */
  icon?: ReactNode
  title: string
  description?: string
  /** Optional action(s) — e.g. a primary button wrapped in a Link. */
  children?: ReactNode
  className?: string
}

/**
 * Centered empty / zero-state block: icon, title (serif), description, and an
 * optional action slot via children.
 */
export default function EmptyState({
  icon,
  title,
  description,
  children,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={[
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-surface-border bg-surface-subtle/60 px-6 py-14 text-center',
        className,
      ].join(' ')}
    >
      {icon && (
        <div className="mb-4 text-4xl leading-none" aria-hidden>
          {icon}
        </div>
      )}
      <h3 className="font-serif text-xl font-semibold text-ink">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm text-ink-muted">{description}</p>
      )}
      {children && <div className="mt-6 flex items-center gap-3">{children}</div>}
    </div>
  )
}
