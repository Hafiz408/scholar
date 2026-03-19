'use client'

import Link from 'next/link'
import type { StudySession } from '@/types'

type SessionState = 'locked' | 'available' | 'in_progress' | 'complete'

function getSessionState(session: StudySession, prevSession?: StudySession): SessionState {
  if (session.status === 'complete') return 'complete'
  if (session.status === 'in_progress') return 'in_progress'
  if (session.session_number === 1) return 'available'
  if (prevSession?.status === 'complete') return 'available'
  return 'locked'
}

const STATE_STYLES: Record<SessionState, string> = {
  locked: 'opacity-50 cursor-not-allowed border-gray-200',
  available: 'border-blue-300 cursor-pointer hover:bg-blue-50',
  in_progress: 'border-yellow-400 bg-yellow-50',
  complete: 'border-green-400 bg-green-50',
}

interface StudyPlanProps {
  sessions: StudySession[]
}

export default function StudyPlan({ sessions }: StudyPlanProps) {
  return (
    <div className="space-y-3">
      {sessions.map((session, index) => {
        const prevSession = index > 0 ? sessions[index - 1] : undefined
        const state = getSessionState(session, prevSession)
        const stateStyle = STATE_STYLES[state]

        const card = (
          <div
            className={`border-2 rounded-lg p-4 flex items-start gap-3 ${stateStyle}`}
          >
            {/* Session number badge */}
            <span className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-700">
              {session.session_number}
            </span>

            {/* Session info */}
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-gray-900 truncate">{session.title}</h3>
              <p className="text-sm text-gray-600">{session.topic}</p>
              <p className="text-xs text-gray-400 mt-1">~{session.estimated_minutes} min</p>
            </div>

            {/* State pill / quiz badge */}
            <div className="flex-shrink-0 flex flex-col items-end gap-1">
              {state === 'locked' && (
                <span className="text-gray-400" aria-label="Locked">
                  {'\uD83D\uDD12'}
                </span>
              )}
              {state === 'available' && (
                <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                  Available
                </span>
              )}
              {state === 'in_progress' && (
                <span className="text-xs px-2 py-1 rounded-full bg-yellow-100 text-yellow-700 font-medium">
                  In Progress
                </span>
              )}
              {state === 'complete' && (
                <>
                  <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700 font-medium">
                    Complete
                  </span>
                  {session.quiz_score != null && (
                    <span className="text-xs px-2 py-1 rounded-full bg-green-600 text-white font-medium">
                      {Math.round(session.quiz_score * 100)}%
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        )

        if (state === 'available' || state === 'in_progress') {
          return (
            <Link key={session.id} href={`/study/${session.id}`}>
              {card}
            </Link>
          )
        }

        return <div key={session.id}>{card}</div>
      })}
    </div>
  )
}
