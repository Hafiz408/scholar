'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { mutate } from 'swr'
import { streamSuperChat } from '@/lib/sse'
import { useSuperThreads, useSuperThread, useSources } from '@/lib/hooks'
import { Button } from '@/components/ui'
import ThreadRail from '@/components/super/ThreadRail'
import MessageBubble from '@/components/super/MessageBubble'
import type { ChatMessage } from '@/types'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function freshThreadId(): string {
  return crypto.randomUUID()
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SuperPage() {
  // On first mount we start a brand-new thread (the rail shows all past history).
  const [activeThreadId, setActiveThreadId] = useState<string>(() => freshThreadId())

  // Local in-memory conversation for the active thread.
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  // Whether we've seeded the message list from the server thread yet.
  // Used to avoid re-seeding on every render.
  const seededThreadIdRef = useRef<string | null>(null)

  const cancelRef = useRef<(() => void) | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // ── Data hooks ──────────────────────────────────────────────────────────────

  const { data: threadList = [], isLoading: threadsLoading } = useSuperThreads()
  // Fetch thread detail only for existing (server-known) threads, i.e. ones that
  // appear in the thread list.  A brand-new local UUID won't be in the list until
  // the first message is sent, so we skip the fetch to avoid a 404.
  const threadExistsOnServer = threadList.some((t) => t.thread_id === activeThreadId)
  const { data: threadDetail } = useSuperThread(
    threadExistsOnServer ? activeThreadId : null
  )

  // ── Source count (optional header badge) ────────────────────────────────────
  const { data: sources = [] } = useSources()
  const readySourceCount = sources.filter((s) => s.status === 'ready').length

  // ── Thread history seeding ───────────────────────────────────────────────────
  // When a user clicks an existing thread in the rail, load its server messages
  // into the local message list exactly once (skip if already seeded, or if
  // we're actively streaming).
  useEffect(() => {
    if (!threadDetail) return
    if (seededThreadIdRef.current === activeThreadId) return
    if (isStreaming) return

    const serverMessages: ChatMessage[] = threadDetail.messages.map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      citations: [],
    }))
    setMessages(serverMessages)
    seededThreadIdRef.current = activeThreadId
  }, [threadDetail, activeThreadId, isStreaming])

  // ── Auto-scroll ──────────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── SSE cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      cancelRef.current?.()
    }
  }, [])

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleNewChat = useCallback(() => {
    cancelRef.current?.()
    cancelRef.current = null
    setIsStreaming(false)
    seededThreadIdRef.current = null
    setMessages([])
    setInput('')
    setActiveThreadId(freshThreadId())
  }, [])

  const handleSelectThread = useCallback(
    (threadId: string) => {
      if (threadId === activeThreadId) return
      cancelRef.current?.()
      cancelRef.current = null
      setIsStreaming(false)
      seededThreadIdRef.current = null
      setMessages([])
      setInput('')
      setActiveThreadId(threadId)
    },
    [activeThreadId]
  )

  const handleSend = useCallback(() => {
    const msg = input.trim()
    if (!msg || isStreaming) return

    setInput('')
    setIsStreaming(true)

    // Optimistically append user + empty assistant bubbles.
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: msg, citations: [] },
      { role: 'assistant', content: '', citations: [] },
    ])

    const cancel = streamSuperChat(
      msg,
      activeThreadId,
      // onToken — append to last assistant bubble
      (token) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + token,
            }
          }
          return updated
        })
      },
      // onCitations — set on last assistant bubble
      (chunks) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = { ...last, citations: chunks }
          }
          return updated
        })
      },
      // onDone — stop streaming, revalidate rail so new/updated thread shows up
      () => {
        setIsStreaming(false)
        mutate('super-threads')
      },
      // onError
      (errMsg) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: `Error: ${errMsg}`,
            }
          }
          return updated
        })
        setIsStreaming(false)
      }
    )

    cancelRef.current = cancel
  }, [input, isStreaming, activeThreadId])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  // ─── Sorted threads — newest-first (API returns them in order, but be safe) ──
  const sortedThreads = [...threadList].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )

  // ─── Streaming indicator on the last assistant bubble ────────────────────────
  const lastMessageIsStreaming =
    isStreaming &&
    messages.length > 0 &&
    messages[messages.length - 1].role === 'assistant'

  return (
    // Full-height two-pane layout; the main <main> in layout is overflow-auto,
    // so we set this container to fill the viewport height.
    <div className="flex h-full overflow-hidden">
      {/* ── Thread rail (left) ─────────────────────────────────────────────── */}
      <ThreadRail
        threads={sortedThreads}
        isLoading={threadsLoading}
        activeThreadId={activeThreadId}
        onNewChat={handleNewChat}
        onSelectThread={handleSelectThread}
      />

      {/* ── Conversation pane (right) ──────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex flex-shrink-0 items-center justify-between border-b border-surface-border bg-surface-card px-6 py-4 shadow-soft">
          <div>
            <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink">
              Super Agent
            </h1>
            <p className="mt-0.5 text-xs text-ink-muted">
              Ask anything across all your indexed sources
            </p>
          </div>
          {readySourceCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-success-500/20 bg-success-50 px-3 py-1 text-xs font-medium text-success-700">
              <span className="h-1.5 w-1.5 rounded-full bg-success-500" aria-hidden />
              {readySourceCount} source{readySourceCount !== 1 ? 's' : ''} ready
            </span>
          )}
        </header>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 text-5xl" aria-hidden>
                ✦
              </div>
              <h2 className="font-serif text-xl font-semibold text-ink">
                What would you like to explore?
              </h2>
              <p className="mt-2 max-w-sm text-sm text-ink-muted">
                Ask a question across all your indexed books and papers. The agent
                will retrieve the most relevant passages and synthesise an answer.
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-5">
              {messages.map((msg, i) => {
                const isLast = i === messages.length - 1
                return (
                  <MessageBubble
                    key={i}
                    message={msg}
                    isStreaming={isLast && lastMessageIsStreaming}
                  />
                )
              })}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input row */}
        <div className="flex-shrink-0 border-t border-surface-border bg-surface-card px-6 py-4">
          <div className="mx-auto flex max-w-2xl items-end gap-3">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask across all your books… (Enter to send, Shift+Enter for newline)"
              disabled={isStreaming}
              className={[
                'flex-1 resize-none rounded-xl border border-surface-border bg-surface px-4 py-3 text-sm text-ink-soft placeholder:text-ink-muted',
                'focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-400/30',
                'disabled:cursor-not-allowed disabled:opacity-50',
                'max-h-36 overflow-y-auto leading-relaxed',
              ].join(' ')}
              style={{
                // Auto-grow height with content up to max-h via scrollHeight
                height: 'auto',
              }}
              onInput={(e) => {
                const target = e.currentTarget
                target.style.height = 'auto'
                target.style.height = `${Math.min(target.scrollHeight, 144)}px`
              }}
            />
            <Button
              variant="primary"
              size="md"
              onClick={handleSend}
              disabled={isStreaming || !input.trim()}
              className="flex-shrink-0"
            >
              {isStreaming ? (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/80 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/80 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/80" />
                </span>
              ) : (
                'Send'
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
