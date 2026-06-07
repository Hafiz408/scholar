'use client'

import { useEffect, useState } from 'react'
import { getSession } from '@/lib/api'
import type { StudySession } from '@/types'
import SessionNotes from '@/components/SessionNotes'
import ChatPanel from '@/components/ChatPanel'
import QuizPanel from '@/components/QuizPanel'
import AdaptiveAlert from '@/components/AdaptiveAlert'
import NotionExportButton from '@/components/NotionExportButton'
import PageHeader from '@/components/ui/PageHeader'
import Card from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Skeleton from '@/components/ui/Skeleton'

interface PageProps {
  params: { sessionId: string }
}

type Mode = 'study' | 'quiz'

const STATUS_TONE = {
  pending: 'neutral',
  in_progress: 'info',
  complete: 'success',
} as const

export default function StudySessionPage({ params }: PageProps) {
  const sessionId = params.sessionId
  const [session, setSession] = useState<StudySession | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('study')
  // undefined = not triggered, null = triggered with no session data
  const [followupSession, setFollowupSession] = useState<StudySession | null | undefined>(undefined)

  useEffect(() => {
    getSession(sessionId)
      .then((data) => setSession(data))
      .catch((err) => setLoadError(err.message ?? 'Failed to load session'))
  }, [sessionId])

  // ── Error state ──────────────────────────────────────────────────────────────
  if (loadError) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <PageHeader
          title="Study Session"
          breadcrumbs={[
            { label: 'Goals', href: '/goals' },
            { label: 'Study plan' },
            { label: 'Session' },
          ]}
        />
        <Card className="border-danger-500/30 bg-danger-50">
          <p className="text-sm font-medium text-danger-600">{loadError}</p>
        </Card>
      </div>
    )
  }

  // ── Loading skeleton ─────────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="flex h-full flex-col px-6 py-6">
        {/* Header skeleton */}
        <div className="mb-8 space-y-3">
          <div className="flex gap-2">
            <Skeleton className="h-3.5 w-16" />
            <Skeleton className="h-3.5 w-3" />
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-3.5 w-3" />
            <Skeleton className="h-3.5 w-20" />
          </div>
          <Skeleton className="h-9 w-80" />
          <Skeleton className="h-4 w-56" />
        </div>
        {/* Two-pane skeleton */}
        <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="flex flex-col gap-3 p-5">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
          </Card>
          <Card className="flex flex-col gap-3 p-5">
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </Card>
        </div>
      </div>
    )
  }

  // ── Derived values ───────────────────────────────────────────────────────────
  const statusTone = STATUS_TONE[session.status] ?? 'neutral'
  const statusLabel =
    session.status === 'in_progress'
      ? 'In progress'
      : session.status === 'complete'
      ? 'Complete'
      : 'Pending'

  const quizScoreLabel =
    session.quiz_score !== undefined && session.quiz_score !== null
      ? `Quiz: ${Math.round(session.quiz_score * 100)}%`
      : null

  // ── Actions slot for PageHeader ──────────────────────────────────────────────
  const headerActions = (
    <>
      {mode === 'study' && (
        <Button
          variant="primary"
          size="sm"
          onClick={() => setMode('quiz')}
        >
          Start Quiz
        </Button>
      )}
      <NotionExportButton goalId={session.goal_id} />
    </>
  )

  // ── Shared page wrapper ──────────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ── Scrollable header + content area ──────────────────────────────── */}
      <div className="flex h-full flex-col overflow-hidden px-6 pt-6">
        {/* Header */}
        <div className="shrink-0">
          <PageHeader
            title={session.title}
            subtitle={session.topic}
            breadcrumbs={[
              { label: 'Goals', href: '/goals' },
              { label: 'Study plan', href: `/goals/${session.goal_id}` },
              { label: `Session ${session.session_number}` },
            ]}
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone}>{statusLabel}</Badge>
                {quizScoreLabel && (
                  <Badge tone={session.quiz_score! >= 0.7 ? 'success' : 'warning'}>
                    {quizScoreLabel}
                  </Badge>
                )}
                {headerActions}
              </div>
            }
          />
        </div>

        {/* AdaptiveAlert — shown when a follow-up session was triggered */}
        {followupSession !== undefined && (
          <div className="mb-4 shrink-0">
            <AdaptiveAlert
              session={followupSession}
              onDismiss={() => setFollowupSession(undefined)}
            />
          </div>
        )}

        {/* ── STUDY MODE: two-pane split ─────────────────────────────────── */}
        {mode === 'study' && (
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 pb-6 lg:grid-cols-2">
            {/* Left pane — Notes */}
            <Card className="flex min-h-0 flex-col overflow-hidden p-0">
              {/* Pane header */}
              <div className="flex shrink-0 items-center justify-between border-b border-surface-border px-5 py-3">
                <h2 className="font-serif text-base font-semibold text-ink">
                  Session Notes
                </h2>
                {session.estimated_minutes && (
                  <span className="text-xs text-ink-muted">
                    ~{session.estimated_minutes} min
                  </span>
                )}
              </div>
              {/* Scrollable notes body */}
              <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                <SessionNotes
                  sessionId={sessionId}
                  initialNotes={session.notes_markdown ?? null}
                />
              </div>
            </Card>

            {/* Right pane — Chat */}
            <Card className="flex min-h-0 flex-col overflow-hidden p-0">
              {/* Pane header */}
              <div className="flex shrink-0 items-center border-b border-surface-border px-5 py-3">
                <h2 className="font-serif text-base font-semibold text-ink">
                  Ask Scholar
                </h2>
              </div>
              {/* Chat fills remaining height */}
              <div className="min-h-0 flex-1 overflow-hidden px-4 py-3">
                <ChatPanel sessionId={sessionId} />
              </div>
            </Card>
          </div>
        )}

        {/* ── QUIZ MODE: full-width takeover ─────────────────────────────── */}
        {mode === 'quiz' && (
          <div className="flex min-h-0 flex-1 flex-col pb-6">
            {/* Back affordance */}
            <div className="mb-4 shrink-0">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setMode('study')}
                className="gap-1.5"
              >
                <svg
                  aria-hidden
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                  className="h-4 w-4"
                >
                  <path
                    fillRule="evenodd"
                    d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06l-3.25-3.25a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z"
                    clipRule="evenodd"
                  />
                </svg>
                Back to session
              </Button>
            </div>

            {/* Quiz card — full width, scrollable */}
            <Card className="min-h-0 flex-1 overflow-y-auto p-6">
              <QuizPanel
                sessionId={sessionId}
                goalId={session.goal_id}
                onFollowupAdded={(s) => {
                  setFollowupSession(s ?? null)
                  // Return to study mode so the alert is visible
                  setMode('study')
                }}
              />
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
