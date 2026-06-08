'use client'

import Link from 'next/link'
import { useGoals } from '@/lib/hooks'
import type { GoalSummary } from '@/types'
import {
  Button,
  Card,
  Badge,
  Skeleton,
  PageHeader,
  EmptyState,
  ProgressRing,
} from '@/components/ui'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(completed: number, total: number): number {
  if (!total) return 0
  return Math.round((completed / total) * 100)
}

function deadlineLabel(days: number): string {
  if (days <= 0) return 'No deadline'
  if (days === 1) return '1 day left'
  if (days <= 7) return `${days} days left`
  const weeks = Math.round(days / 7)
  return `~${weeks} week${weeks !== 1 ? 's' : ''} left`
}

function sortGoals(goals: GoalSummary[]): GoalSummary[] {
  return [...goals].sort((a, b) => {
    // Active first
    if (a.status === 'active' && b.status !== 'active') return -1
    if (a.status !== 'active' && b.status === 'active') return 1
    // Within same status: most recent first (created_at desc)
    const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
    const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
    return bTime - aTime
  })
}

// ─── Skeleton card ─────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="flex flex-col items-center gap-2 py-2">
        <Skeleton className="h-[72px] w-[72px] rounded-full" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-20" />
      </div>
    </Card>
  )
}

// ─── Goal card ─────────────────────────────────────────────────────────────────

function GoalCard({ goal }: { goal: GoalSummary }) {
  const progress = pct(goal.completed_sessions, goal.total_sessions)
  const isComplete = goal.status === 'complete'
  const nextSession = goal.completed_sessions + 1

  const progressLabel =
    isComplete ? (
      <span className="text-success-600 text-base leading-none">✓</span>
    ) : (
      `${progress}%`
    )

  const sessionLabel = isComplete
    ? 'Completed'
    : goal.total_sessions > 0
    ? `Session ${nextSession} of ${goal.total_sessions}`
    : 'No sessions yet'

  return (
    <Link href={`/goals/${goal.id}`} className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 rounded-xl">
      <Card
        interactive
        className="flex h-full flex-col gap-4 group-focus-visible:ring-2 group-focus-visible:ring-primary-400"
      >
        {/* Header row: title + status badge */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="font-serif text-lg font-semibold leading-snug text-ink line-clamp-2">
              {goal.title}
            </h2>
            <p className="mt-0.5 text-sm text-ink-muted line-clamp-1">{goal.topic}</p>
          </div>
          <Badge
            tone={isComplete ? 'success' : 'info'}
            className="mt-0.5 shrink-0 capitalize"
          >
            {isComplete ? 'Complete' : 'Active'}
          </Badge>
        </div>

        {/* Progress ring — centered */}
        <div className="flex flex-col items-center gap-1.5 py-2">
          <ProgressRing
            value={progress}
            size={80}
            strokeWidth={7}
            label={progressLabel}
          />
          <p className="text-sm text-ink-soft">{sessionLabel}</p>
        </div>

        {/* Footer: deadline */}
        <div className="mt-auto flex items-center justify-between border-t border-surface-border pt-3 text-xs text-ink-muted">
          <span>{goal.level}</span>
          <span>{deadlineLabel(goal.deadline_days)}</span>
        </div>
      </Card>
    </Link>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function GoalsDashboard() {
  const { data: goals, isLoading, error } = useGoals()

  return (
    <div className="px-8 py-8">
      <PageHeader
        title="Goals"
        subtitle="Track your study goals and session progress."
        actions={
          <Link href="/goals/new">
            <Button variant="primary" size="md">
              + New Goal
            </Button>
          </Link>
        }
      />

      {/* Error state */}
      {error && (
        <p className="text-sm text-danger-600">
          Failed to load goals: {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      )}

      {/* Loading state — skeleton grid */}
      {isLoading && !error && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && goals && goals.length === 0 && (
        <EmptyState
          icon="🎯"
          title="No study goals yet"
          description="Create your first goal and Scholar will build a personalised study plan for you."
        >
          <Link href="/goals/new">
            <Button variant="primary">Create your first goal</Button>
          </Link>
        </EmptyState>
      )}

      {/* Goal card grid */}
      {!isLoading && !error && goals && goals.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {sortGoals(goals).map((goal) => (
            <GoalCard key={goal.id} goal={goal} />
          ))}
        </div>
      )}
    </div>
  )
}
