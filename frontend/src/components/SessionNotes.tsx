'use client'

import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamNotes } from '@/lib/sse'

interface SessionNotesProps {
  sessionId: string
  initialNotes?: string | null
}

export default function SessionNotes({ sessionId, initialNotes }: SessionNotesProps) {
  const [notesContent, setNotesContent] = useState<string>(initialNotes ?? '')
  const [streaming, setStreaming] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const hasStarted = useRef(false)

  useEffect(() => {
    // If notes are already available, show them without re-streaming
    if (initialNotes) {
      setNotesContent(initialNotes)
      return
    }

    // Guard against double-invocation (StrictMode, etc.)
    if (hasStarted.current) return
    hasStarted.current = true
    setStreaming(true)
    setError(null)

    const cleanup = streamNotes(
      sessionId,
      // onChunk: append chunk to content
      (chunk: string) => {
        setNotesContent((prev) => prev + chunk)
      },
      // onDone
      () => {
        setStreaming(false)
      },
      // onError
      (msg: string) => {
        setStreaming(false)
        setError(msg)
      }
    )

    return () => {
      cleanup()
      // Reset guard so that if sessionId changes, streaming can restart
      hasStarted.current = false
    }
  }, [sessionId, initialNotes])

  return (
    <div className="prose prose-sm max-w-none">
      {streaming && notesContent.length === 0 && (
        <p className="text-gray-500 text-sm animate-pulse">Generating notes...</p>
      )}

      {notesContent.length > 0 && (
        <>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{notesContent}</ReactMarkdown>
          {streaming && (
            <span className="text-gray-400 text-sm">...</span>
          )}
        </>
      )}

      {error && (
        <p className="text-red-500 text-sm mt-2">{error}</p>
      )}
    </div>
  )
}
