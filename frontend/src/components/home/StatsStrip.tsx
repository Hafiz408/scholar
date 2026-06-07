'use client'

import Link from 'next/link'
import { useGoals, useSources, useSuperThreads } from '@/lib/hooks'
import Card from '@/components/ui/Card'
import Skeleton from '@/components/ui/Skeleton'

interface StatCardProps {
  href: string
  label: string
  icon: string
  value: number | undefined
  isLoading: boolean
  error: unknown
}

function StatCard({ href, label, icon, value, isLoading, error }: StatCardProps) {
  return (
    <Link href={href} className="block">
      <Card
        interactive
        className="flex flex-col items-start gap-1 p-5"
      >
        <span className="text-2xl leading-none" aria-hidden>
          {icon}
        </span>
        <div className="mt-2">
          {isLoading ? (
            <Skeleton className="h-7 w-10" />
          ) : error ? (
            <span className="text-xl font-bold text-danger-500">—</span>
          ) : (
            <span className="font-serif text-2xl font-bold text-ink">
              {value ?? 0}
            </span>
          )}
        </div>
        <p className="text-xs text-ink-muted">{label}</p>
      </Card>
    </Link>
  )
}

/**
 * Three-column stats strip: indexed sources, goals in progress, super threads.
 * Each card is a link to its respective section.
 */
export default function StatsStrip() {
  const { data: goalsData, isLoading: goalsLoading, error: goalsError } = useGoals()
  const { data: sourcesData, isLoading: sourcesLoading, error: sourcesError } = useSources()
  const { data: threadsData, isLoading: threadsLoading, error: threadsError } = useSuperThreads()

  const indexedCount = sourcesData
    ? sourcesData.filter((s) => s.status === 'ready').length
    : undefined

  const activeGoalsCount = goalsData
    ? goalsData.filter((g) => g.status !== 'complete').length
    : undefined

  const threadsCount = threadsData ? threadsData.length : undefined

  return (
    <section aria-label="Overview statistics" className="mb-10">
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          href="/knowledge"
          label="Sources indexed"
          icon="📚"
          value={indexedCount}
          isLoading={sourcesLoading}
          error={sourcesError}
        />
        <StatCard
          href="/goals"
          label="Goals in progress"
          icon="🎯"
          value={activeGoalsCount}
          isLoading={goalsLoading}
          error={goalsError}
        />
        <StatCard
          href="/super"
          label="Super threads"
          icon="✨"
          value={threadsCount}
          isLoading={threadsLoading}
          error={threadsError}
        />
      </div>
    </section>
  )
}
