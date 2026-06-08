'use client'

import Link from 'next/link'
import { useGoals } from '@/lib/hooks'
import Skeleton from '@/components/ui/Skeleton'
import GoalCard from './GoalCard'

const MAX_VISIBLE = 4

/**
 * "Your goals" section — shows up to 4 active (non-complete) goals with
 * Skeleton loading states and a graceful empty state.
 */
export default function ActiveGoals() {
  const { data, isLoading, error } = useGoals()

  const activeGoals = data
    ? data.filter((g) => g.status !== 'complete').slice(0, MAX_VISIBLE)
    : []

  return (
    <section aria-labelledby="goals-heading" className="mb-10">
      <div className="mb-4 flex items-center justify-between">
        <h2
          id="goals-heading"
          className="font-serif text-xl font-semibold text-ink"
        >
          Your goals
        </h2>
        {!isLoading && !error && data && data.length > 0 && (
          <Link
            href="/goals"
            className="text-sm font-medium text-primary-600 transition-colors hover:text-primary-700"
          >
            View all goals →
          </Link>
        )}
      </div>

      {/* Error state */}
      {error && (
        <p className="text-sm text-danger-600">
          Could not load goals. Please try refreshing the page.
        </p>
      )}

      {/* Loading skeletons */}
      {isLoading && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-xl border border-surface-border bg-surface-card p-6 shadow-card">
              <div className="flex gap-5">
                <Skeleton className="h-[60px] w-[60px] shrink-0 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-5 w-4/5" />
                  <Skeleton className="h-3 w-3/5" />
                  <Skeleton className="h-3 w-2/5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Active goals grid */}
      {!isLoading && !error && activeGoals.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {activeGoals.map((goal) => (
            <GoalCard key={goal.id} goal={goal} />
          ))}
        </div>
      )}

      {/* Empty state — no active goals */}
      {!isLoading && !error && data && activeGoals.length === 0 && (
        <p className="text-sm text-ink-muted">
          No active goals yet.{' '}
          <Link
            href="/goals/new"
            className="font-medium text-primary-600 underline-offset-2 hover:underline"
          >
            Create your first goal →
          </Link>
        </p>
      )}
    </section>
  )
}
