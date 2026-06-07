'use client'

import Link from 'next/link'
import { useGoals, useSources } from '@/lib/hooks'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'

import IntroBanner from '@/components/home/IntroBanner'
import QuickActions from '@/components/home/QuickActions'
import ActiveGoals from '@/components/home/ActiveGoals'
import StatsStrip from '@/components/home/StatsStrip'

/**
 * Scholar Home page — "Hybrid Dashboard"
 *
 * Layout (top → bottom):
 *   1. Dismissible intro banner (newcomers only)
 *   2. Greeting + quick-action buttons
 *   3. Active goals summary (up to 4, with skeletons + empty state)
 *   4. Stats strip (indexed sources / goals / super threads)
 *
 * Overall empty state: when there are no goals AND no sources, a centred
 * EmptyState replaces sections 3–4 and prompts the user to upload their
 * first source. The banner still renders above it.
 */
export default function Home() {
  const { data: goalsData, isLoading: goalsLoading } = useGoals()
  const { data: sourcesData, isLoading: sourcesLoading } = useSources()

  // Determine overall "empty workspace" — only after both loads resolve
  const bothLoaded = !goalsLoading && !sourcesLoading
  const hasGoals = goalsData && goalsData.length > 0
  const hasSources = sourcesData && sourcesData.length > 0
  const isEmptyWorkspace = bothLoaded && !hasGoals && !hasSources

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* ── 1. Dismissible intro banner ─────────────────────────────────────── */}
      <IntroBanner />

      {/* ── 2. Greeting + quick actions ─────────────────────────────────────── */}
      <QuickActions greeting="Welcome to Scholar" />

      {/* ── Overall empty state ─────────────────────────────────────────────── */}
      {isEmptyWorkspace ? (
        <EmptyState
          icon="📖"
          title="Start by adding your study material"
          description="Upload a PDF or paste a URL and Scholar will index it, letting you create adaptive study goals with quizzes and guided sessions."
          className="mt-4"
        >
          <Link href="/knowledge">
            <Button variant="primary">Upload your first source</Button>
          </Link>
          <Link href="/goals/new">
            <Button variant="secondary">Create a goal</Button>
          </Link>
        </EmptyState>
      ) : (
        <>
          {/* ── 3. Active goals summary ───────────────────────────────────────── */}
          <ActiveGoals />

          {/* ── 4. Stats strip ────────────────────────────────────────────────── */}
          <StatsStrip />
        </>
      )}
    </div>
  )
}
