'use client'

import type { StudySession } from '@/types'

interface AdaptiveAlertProps {
  session: StudySession | null
  onDismiss: () => void
}

export default function AdaptiveAlert({ session, onDismiss }: AdaptiveAlertProps) {
  return (
    <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 flex items-start justify-between gap-3">
      <div>
        <p className="text-amber-800 font-medium text-sm">Follow-up session added</p>
        {session && (
          <p className="text-amber-700 text-sm mt-0.5">
            A new session &quot;{session.title}&quot; has been added to your study plan to reinforce weak areas.
          </p>
        )}
        {!session && (
          <p className="text-amber-700 text-sm mt-0.5">
            A follow-up session has been added to your study plan.
          </p>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="text-amber-600 hover:text-amber-800 text-lg leading-none flex-shrink-0 mt-0.5"
        aria-label="Dismiss"
      >
        &times;
      </button>
    </div>
  )
}
