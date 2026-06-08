'use client'

import { useState, useEffect } from 'react'
import { getGoalPlan } from '@/lib/api'
import ProgressBar from '@/components/ProgressBar'
import StudyPlan from '@/components/StudyPlan'
import TestPanel from '@/components/TestPanel'
import NotionExportButton from '@/components/NotionExportButton'
import {
  Card,
  PageHeader,
  ProgressRing,
  Skeleton,
} from '@/components/ui'
import type { StudyPlan as StudyPlanType } from '@/types'

// ─── Progress summary card ────────────────────────────────────────────────────

interface ProgressSummaryProps {
  completed: number
  total: number
  avgQuizScore: number | null
}

function ProgressSummary({ completed, total, avgQuizScore }: ProgressSummaryProps) {
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0
  const isComplete = total > 0 && completed === total

  const ringLabel = isComplete ? (
    <span className="text-success-600 text-base leading-none">✓</span>
  ) : (
    `${progress}%`
  )

  return (
    <Card className="flex flex-wrap items-center gap-6 sm:gap-8">
      {/* Ring */}
      <ProgressRing
        value={progress}
        size={88}
        strokeWidth={8}
        label={ringLabel}
      />

      {/* Stat group */}
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-ink-muted uppercase tracking-wide text-[0.7rem]">
          Sessions
        </p>
        <p className="font-serif text-2xl font-semibold text-ink leading-none">
          {completed}
          <span className="text-base text-ink-muted font-sans font-normal"> / {total}</span>
        </p>
        <p className="text-sm text-ink-soft">
          {isComplete ? 'All sessions complete' : `${total - completed} remaining`}
        </p>
      </div>

      {/* Average quiz score — only when at least one session has a score */}
      {avgQuizScore !== null && (
        <div className="flex flex-col gap-1 sm:border-l sm:border-surface-border sm:pl-8">
          <p className="text-sm font-medium text-ink-muted uppercase tracking-wide text-[0.7rem]">
            Avg. Quiz Score
          </p>
          <p className="font-serif text-2xl font-semibold text-ink leading-none">
            {avgQuizScore}%
          </p>
          <p className="text-sm text-ink-soft">across completed sessions</p>
        </div>
      )}
    </Card>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-2xl px-8 py-8 space-y-6">
      {/* Header skeleton */}
      <div className="space-y-3 mb-8">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-40" />
      </div>
      {/* Progress summary skeleton */}
      <Card className="flex items-center gap-6">
        <Skeleton className="h-[88px] w-[88px] rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
      </Card>
      {/* Session list skeleton */}
      <div className="space-y-3 mt-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function GoalDetailPage({ params }: { params: { id: string } }) {
  const goalId = params.id

  const [plan, setPlan] = useState<StudyPlanType | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getGoalPlan(goalId)
      .then(setPlan)
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load goal')
      })
  }, [goalId])

  // ── Error ──
  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-8 py-8">
        <p className="text-sm text-danger-600">
          Failed to load goal: {error}
        </p>
      </div>
    )
  }

  // ── Loading ──
  if (!plan) {
    return <DetailSkeleton />
  }

  // ── Derived values ──
  const completed = plan.sessions.filter((s) => s.status === 'complete').length
  const total = plan.sessions.length
  const allSessionsComplete =
    total > 0 && plan.sessions.every((s) => s.status === 'complete')

  // Average quiz score: only sessions that are complete AND have a quiz_score
  const scoredSessions = plan.sessions.filter(
    (s) => s.status === 'complete' && s.quiz_score != null
  )
  const avgQuizScore =
    scoredSessions.length > 0
      ? Math.round(
          (scoredSessions.reduce((sum, s) => sum + (s.quiz_score ?? 0), 0) /
            scoredSessions.length) *
            100
        )
      : null

  return (
    <div className="mx-auto max-w-2xl px-8 py-8">
      {/* ── Page header ── */}
      <PageHeader
        title={plan.goal.title}
        subtitle={plan.goal.topic}
        breadcrumbs={[
          { label: 'Goals', href: '/goals' },
          { label: plan.goal.title },
        ]}
      />

      {/* ── Overall progress summary ── */}
      <ProgressSummary
        completed={completed}
        total={total}
        avgQuizScore={avgQuizScore}
      />

      {/* ── Study sessions ── */}
      <section className="mt-8">
        <h2 className="mb-4 font-serif text-lg font-semibold text-ink">
          Study Sessions
        </h2>
        <StudyPlan sessions={plan.sessions} />
      </section>

      {/* ── Notion export ── */}
      <div className="mt-6">
        <NotionExportButton
          goalId={goalId}
          initialNotionUrl={plan.goal.notion_page_url}
        />
      </div>

      {/* ── Final test (shown only when all sessions are complete) ── */}
      {allSessionsComplete && (
        <div className="mt-6">
          <TestPanel goalId={goalId} />
        </div>
      )}
    </div>
  )
}
