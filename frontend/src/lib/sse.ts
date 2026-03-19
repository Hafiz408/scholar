import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { RetrievedChunk } from '@/types'

/**
 * Stream notes for a session via POST /sessions/{sessionId}/start.
 * Returns a cleanup function for useEffect.
 */
export function streamNotes(
  sessionId: string,
  onChunk: (chunk: string) => void,
  onDone: (totalChars: number) => void,
  onError: (msg: string) => void
): () => void {
  const ctrl = new AbortController()

  fetchEventSource(`/api/sessions/${sessionId}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal: ctrl.signal,
    onmessage(ev) {
      if (ev.event === 'notes_chunk') {
        const data = JSON.parse(ev.data)
        onChunk(data.content)
      } else if (ev.event === 'notes_done') {
        const data = JSON.parse(ev.data)
        ctrl.abort()
        onDone(data.total_chars)
      }
    },
    onerror(err) {
      // fetchEventSource will retry on network errors; abort to stop retries
      ctrl.abort()
      onError('Notes stream error')
      throw err // re-throw to prevent automatic retry
    },
    openWhenHidden: true,
  }).catch(() => {
    // Swallow AbortError from ctrl.abort() — not a real error
  })

  return () => ctrl.abort()
}

/**
 * Stream chat response for a session via POST /sessions/{sessionId}/chat.
 * Returns a cleanup function for useEffect.
 */
export function streamChat(
  sessionId: string,
  message: string,
  onToken: (token: string) => void,
  onCitations: (chunks: RetrievedChunk[]) => void,
  onDone: () => void,
  onError: (msg: string) => void
): () => void {
  const ctrl = new AbortController()

  fetchEventSource(`/api/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal: ctrl.signal,
    onmessage(ev) {
      if (ev.event === 'token') {
        const data = JSON.parse(ev.data)
        onToken(data.content)
      } else if (ev.event === 'citations') {
        const data = JSON.parse(ev.data)
        onCitations(data.chunks)
      } else if (ev.event === 'done') {
        ctrl.abort()
        onDone()
      }
    },
    onerror(err) {
      ctrl.abort()
      onError('Chat stream error')
      throw err // re-throw to prevent automatic retry
    },
    openWhenHidden: true,
  }).catch(() => {
    // Swallow AbortError from ctrl.abort()
  })

  return () => ctrl.abort()
}
