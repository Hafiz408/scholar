'use client'

import { Button, Skeleton } from '@/components/ui'
import type { SuperThreadSummary } from '@/types'

interface ThreadRailProps {
  threads: SuperThreadSummary[]
  isLoading: boolean
  activeThreadId: string
  onNewChat: () => void
  onSelectThread: (threadId: string) => void
}

/** Format a UTC ISO timestamp to a short relative or absolute label. */
function formatRelative(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  if (isNaN(then)) return ''
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60_000)
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return new Date(isoString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function ThreadRail({
  threads,
  isLoading,
  activeThreadId,
  onNewChat,
  onSelectThread,
}: ThreadRailProps) {
  return (
    <aside className="flex h-full w-[260px] flex-shrink-0 flex-col border-r border-surface-border bg-surface-subtle">
      {/* New chat button */}
      <div className="flex-shrink-0 p-3">
        <Button
          variant="secondary"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={onNewChat}
        >
          <span className="text-base leading-none" aria-hidden>＋</span>
          New chat
        </Button>
      </div>

      {/* Divider */}
      <div className="flex-shrink-0 border-t border-surface-border" />

      {/* Thread list — scrollable */}
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading ? (
          <div className="space-y-2 px-3 pt-1">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1.5">
                <Skeleton className="h-3.5 w-full" />
                <Skeleton className="h-3 w-2/3" />
              </div>
            ))}
          </div>
        ) : threads.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-ink-muted">
            No conversations yet.
          </p>
        ) : (
          <ul className="space-y-0.5 px-2">
            {threads.map((thread) => {
              const isActive = thread.thread_id === activeThreadId
              return (
                <li key={thread.thread_id}>
                  <button
                    onClick={() => onSelectThread(thread.thread_id)}
                    className={[
                      'group w-full rounded-xl px-3 py-2.5 text-left transition-colors',
                      isActive
                        ? 'bg-primary-100 text-ink'
                        : 'text-ink-soft hover:bg-surface-card hover:text-ink',
                    ].join(' ')}
                  >
                    <p
                      className={[
                        'truncate text-sm font-medium leading-snug',
                        isActive ? 'text-primary-700' : '',
                      ].join(' ')}
                    >
                      {thread.title?.trim() || 'Untitled'}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {formatRelative(thread.updated_at)}
                      {thread.message_count > 0 && (
                        <> · {thread.message_count} msg{thread.message_count !== 1 ? 's' : ''}</>
                      )}
                    </p>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}
