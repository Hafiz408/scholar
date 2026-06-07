import type { ReactNode } from 'react'
import Link from 'next/link'

export interface Breadcrumb {
  label: string
  href?: string
}

export interface PageHeaderProps {
  title: string
  subtitle?: string
  /** Optional breadcrumb trail rendered above the title. */
  breadcrumbs?: Breadcrumb[]
  /** Optional actions rendered on the right (e.g. a primary button). */
  actions?: ReactNode
}

/**
 * Page heading block: optional breadcrumbs, a serif title, optional subtitle,
 * and an optional right-aligned actions slot.
 */
export default function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
}: PageHeaderProps) {
  return (
    <header className="mb-8">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-3">
          <ol className="flex flex-wrap items-center gap-1.5 text-sm text-ink-muted">
            {breadcrumbs.map((crumb, i) => {
              const last = i === breadcrumbs.length - 1
              return (
                <li key={`${crumb.label}-${i}`} className="flex items-center gap-1.5">
                  {crumb.href && !last ? (
                    <Link
                      href={crumb.href}
                      className="transition-colors hover:text-primary-700"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span className={last ? 'text-ink-soft' : undefined}>
                      {crumb.label}
                    </span>
                  )}
                  {!last && <span aria-hidden className="text-surface-ring">/</span>}
                </li>
              )
            })}
          </ol>
        </nav>
      )}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 max-w-2xl text-base text-ink-muted">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}
