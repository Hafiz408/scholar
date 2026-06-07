import Link from 'next/link'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import ProgressRing from '@/components/ui/ProgressRing'
import type { GoalSummary } from '@/types'

type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

const LEVEL_TONE: Record<string, BadgeTone> = {
  beginner: 'success',
  intermediate: 'warning',
  advanced: 'danger',
}

interface GoalCardProps {
  goal: GoalSummary
}

/**
 * A compact card for one active goal — shows title, topic, level badge,
 * a ProgressRing, and the "Resume" session indicator.
 */
export default function GoalCard({ goal }: GoalCardProps) {
  const pct =
    goal.total_sessions > 0
      ? Math.round((goal.completed_sessions / goal.total_sessions) * 100)
      : 0

  const nextSession = goal.completed_sessions + 1

  return (
    <Link href={`/goals/${goal.id}`} className="block">
      <Card interactive className="flex gap-5">
        {/* Progress ring */}
        <div className="shrink-0 self-center">
          <ProgressRing
            value={pct}
            size={60}
            strokeWidth={5}
            label={
              <span className="text-xs font-semibold text-ink">
                {pct}%
              </span>
            }
          />
        </div>

        {/* Goal info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={LEVEL_TONE[goal.level] ?? 'neutral'}>
              {goal.level}
            </Badge>
          </div>

          <h3 className="mt-1.5 font-serif text-base font-semibold leading-snug text-ink line-clamp-2">
            {goal.title}
          </h3>

          <p className="mt-0.5 text-sm text-ink-muted line-clamp-1">
            {goal.topic}
          </p>

          <p className="mt-2 text-xs text-ink-muted">
            Resume &middot; Session{' '}
            <span className="font-medium text-ink-soft">
              {nextSession}
            </span>{' '}
            of{' '}
            <span className="font-medium text-ink-soft">
              {goal.total_sessions}
            </span>
          </p>
        </div>
      </Card>
    </Link>
  )
}
