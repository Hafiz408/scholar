import Link from 'next/link'
import Button from '@/components/ui/Button'

interface QuickAction {
  label: string
  icon: string
  href: string
  variant: 'primary' | 'secondary' | 'ghost'
}

const ACTIONS: QuickAction[] = [
  { label: 'New Goal', icon: '＋', href: '/goals/new', variant: 'primary' },
  { label: 'Upload Sources', icon: '＋', href: '/knowledge', variant: 'secondary' },
  { label: 'Ask Super Agent', icon: '🤖', href: '/super', variant: 'ghost' },
]

interface QuickActionsProps {
  /** Shown as the left-side greeting */
  greeting: string
}

/**
 * Greeting headline + a compact row of primary quick-action buttons.
 */
export default function QuickActions({ greeting }: QuickActionsProps) {
  return (
    <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">
        {greeting}
      </h1>

      <div className="flex flex-wrap items-center gap-2">
        {ACTIONS.map((action) => (
          <Link key={action.href} href={action.href}>
            <Button variant={action.variant} size="sm">
              <span aria-hidden>{action.icon}</span>
              {action.label}
            </Button>
          </Link>
        ))}
      </div>
    </div>
  )
}
