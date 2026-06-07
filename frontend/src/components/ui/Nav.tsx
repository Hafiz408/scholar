'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface NavItem {
  href: string
  label: string
  icon: string
}

const ITEMS: NavItem[] = [
  { href: '/', label: 'Home', icon: '🏠' },
  { href: '/knowledge', label: 'Knowledge', icon: '📚' },
  { href: '/goals', label: 'Goals', icon: '🎯' },
  { href: '/super', label: 'Super Agent', icon: '✨' },
]

/**
 * Active when the pathname equals the href, or (for non-root links) begins with
 * `href/` so nested routes (e.g. /goals/123) keep their parent highlighted.
 */
function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

export default function Nav() {
  const pathname = usePathname()

  return (
    <nav className="flex h-full w-56 flex-shrink-0 flex-col gap-1 border-r border-surface-border bg-surface-card p-4">
      {/* Wordmark */}
      <Link href="/" className="mb-6 mt-1 px-2">
        <span className="font-serif text-2xl font-semibold tracking-tight text-ink">
          Scholar
        </span>
        <span className="ml-1 align-super text-primary-600">.</span>
      </Link>

      <div className="px-2 pb-1 text-[0.7rem] font-medium uppercase tracking-wider text-ink-muted">
        Menu
      </div>

      {ITEMS.map((item) => {
        const active = isActive(pathname, item.href)
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? 'page' : undefined}
            className={[
              'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all',
              active
                ? 'bg-primary-50 text-primary-700 shadow-soft'
                : 'text-ink-soft hover:bg-surface-subtle hover:text-ink',
            ].join(' ')}
          >
            <span
              className={[
                'text-base leading-none transition-transform',
                active ? '' : 'opacity-80 group-hover:scale-110',
              ].join(' ')}
              aria-hidden
            >
              {item.icon}
            </span>
            <span>{item.label}</span>
            {active && (
              <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary-600" aria-hidden />
            )}
          </Link>
        )
      })}

      <div className="mt-auto px-2 pt-4 text-[0.7rem] leading-relaxed text-ink-muted">
        Your AI study companion
      </div>
    </nav>
  )
}
