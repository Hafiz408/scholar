'use client'

import { useEffect, useState } from 'react'
import { getSession } from '@/lib/api'
import type { StudySession } from '@/types'
import SessionNotes from '@/components/SessionNotes'
import ChatPanel from '@/components/ChatPanel'
import QuizPanel from '@/components/QuizPanel'
import AdaptiveAlert from '@/components/AdaptiveAlert'

interface PageProps {
  params: { sessionId: string }
}

export default function StudySessionPage({ params }: PageProps) {
  const sessionId = params.sessionId
  const [session, setSession] = useState<StudySession | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  // undefined = not triggered, null = triggered with no session data, StudySession = triggered with session data
  const [followupSession, setFollowupSession] = useState<StudySession | null | undefined>(undefined)

  useEffect(() => {
    getSession(sessionId)
      .then((data) => setSession(data))
      .catch((err) => setLoadError(err.message ?? 'Failed to load session'))
  }, [sessionId])

  if (loadError) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-500">{loadError}</p>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500 animate-pulse">Loading session...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {followupSession !== undefined && (
        <div className="px-4 pt-4">
          <AdaptiveAlert
            session={followupSession}
            onDismiss={() => setFollowupSession(undefined)}
          />
        </div>
      )}
      <div className="grid grid-cols-3 gap-4 h-full p-4 overflow-hidden">
        {/* Notes panel */}
        <div className="col-span-1 overflow-y-auto border rounded-lg p-4">
          <h2 className="font-semibold mb-3">Notes</h2>
          <SessionNotes
            sessionId={sessionId}
            initialNotes={session.notes_markdown ?? null}
          />
        </div>

        {/* Chat panel */}
        <div className="col-span-1 border rounded-lg p-4 flex flex-col overflow-hidden">
          <h2 className="font-semibold mb-3">Chat</h2>
          <ChatPanel sessionId={sessionId} />
        </div>

        {/* Quiz panel */}
        <div className="col-span-1 overflow-y-auto border rounded-lg p-4">
          <h2 className="font-semibold mb-3">Quiz</h2>
          {session && (
            <QuizPanel
              sessionId={sessionId}
              goalId={session.goal_id}
              onFollowupAdded={(s) => setFollowupSession(s ?? null)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
