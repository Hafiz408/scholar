import type { RetrievedChunk } from '@/types'

/**
 * Minimal SSE parser for a ReadableStream of text.
 * Yields parsed { event, data } objects from the stream.
 */
async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<{ event: string; data: string }> {
  const decoder = new TextDecoder()
  let buf = ''
  let event = 'message'

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        yield { event, data: line.slice(5).trim() }
        event = 'message'
      }
    }
  }
}

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

  ;(async () => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        onError(`Notes stream failed: ${res.status}`)
        return
      }
      for await (const { event, data } of parseSSE(res.body.getReader())) {
        if (event === 'notes_chunk') {
          const parsed = JSON.parse(data) as { content: string }
          onChunk(parsed.content)
        } else if (event === 'notes_done') {
          const parsed = JSON.parse(data) as { total_chars: number }
          onDone(parsed.total_chars)
          break
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        onError('Notes stream error')
      }
    }
  })()

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

  ;(async () => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        onError(`Chat stream failed: ${res.status}`)
        return
      }
      for await (const { event, data } of parseSSE(res.body.getReader())) {
        if (event === 'token') {
          const parsed = JSON.parse(data) as { content: string }
          onToken(parsed.content)
        } else if (event === 'citations') {
          const parsed = JSON.parse(data) as { chunks: RetrievedChunk[] }
          onCitations(parsed.chunks)
        } else if (event === 'done') {
          onDone()
          break
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        onError('Chat stream error')
      }
    }
  })()

  return () => ctrl.abort()
}

/**
 * Stream super agent chat response via POST /super/chat/stream.
 * thread_id must be a localStorage UUID (per SUP-03 — never generate server-side).
 * Returns a cleanup function for useEffect.
 */
export function streamSuperChat(
  message: string,
  threadId: string,
  onToken: (token: string) => void,
  onCitations: (chunks: RetrievedChunk[]) => void,
  onDone: () => void,
  onError: (msg: string) => void
): () => void {
  const ctrl = new AbortController()

  ;(async () => {
    try {
      const res = await fetch('/api/super/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, thread_id: threadId }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        onError(`Super chat stream failed: ${res.status}`)
        return
      }
      for await (const { event, data } of parseSSE(res.body.getReader())) {
        if (event === 'token') {
          const parsed = JSON.parse(data) as { content: string }
          onToken(parsed.content)
        } else if (event === 'citations') {
          const parsed = JSON.parse(data) as { chunks: RetrievedChunk[] }
          onCitations(parsed.chunks)
        } else if (event === 'done') {
          onDone()
          break
        } else if (event === 'error') {
          onError(data)
          break
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        onError('Super chat stream error')
      }
    }
  })()

  return () => ctrl.abort()
}
