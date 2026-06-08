'use client'

import { useEffect, useRef, useState } from 'react'
import { streamChat } from '@/lib/sse'
import type { RetrievedChunk } from '@/types'

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: RetrievedChunk[]
  streaming?: boolean
}

interface ChatPanelProps {
  sessionId: string
}

// ─── Citation chip + expandable detail ────────────────────────────────────────

interface CitationChipProps {
  chunk: RetrievedChunk
  expanded: boolean
  onToggle: () => void
}

function CitationChip({ chunk, expanded, onToggle }: CitationChipProps) {
  const methodLabel =
    chunk.retrieval_method === 'pageindex'
      ? 'PageIndex'
      : chunk.retrieval_method === 'vector'
      ? 'Vector'
      : 'Hybrid'

  return (
    <div className="max-w-full">
      {/* The clickable chip */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        title={`${chunk.source_title}${chunk.page_number ? ` · p.${chunk.page_number}` : ''} — click to ${expanded ? 'hide' : 'show'} excerpt`}
        className={[
          'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-all',
          'border ring-inset focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400',
          expanded
            ? 'border-primary-300 bg-primary-50 text-primary-700 ring-primary-200/60'
            : 'border-surface-border bg-surface-subtle text-ink-muted hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700',
        ].join(' ')}
      >
        {/* Source icon */}
        <svg
          aria-hidden
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="h-3 w-3 shrink-0"
        >
          <path d="M3 3.5A1.5 1.5 0 0 1 4.5 2h4.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12A1.5 1.5 0 0 1 13 5.62V12.5A1.5 1.5 0 0 1 11.5 14h-7A1.5 1.5 0 0 1 3 12.5v-9Z" />
        </svg>

        <span className="max-w-[14ch] truncate">{chunk.source_title}</span>

        {chunk.page_number != null && (
          <span className="opacity-60">p.{chunk.page_number}</span>
        )}

        {/* Chevron */}
        <svg
          aria-hidden
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={['h-3 w-3 shrink-0 transition-transform', expanded ? 'rotate-180' : ''].join(' ')}
        >
          <path
            fillRule="evenodd"
            d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Expanded excerpt panel */}
      {expanded && (
        <div className="mt-1.5 rounded-xl border border-primary-200 bg-primary-50/60 p-3 text-xs shadow-soft">
          {/* Source meta row */}
          <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-primary-600">
            <span className="font-semibold">{chunk.source_title}</span>
            {chunk.page_number != null && (
              <span className="text-primary-500">Page {chunk.page_number}</span>
            )}
            {chunk.section_title && (
              <>
                <span className="text-primary-300">·</span>
                <span className="italic text-primary-500">{chunk.section_title}</span>
              </>
            )}
            <span className="ml-auto shrink-0 rounded-full border border-primary-200 bg-white/70 px-2 py-0.5 text-[10px] font-medium text-primary-600">
              {methodLabel}
            </span>
          </div>

          {/* Excerpt text */}
          {chunk.content ? (
            <p className="leading-relaxed text-ink-soft">{chunk.content}</p>
          ) : (
            <p className="italic text-ink-muted">No excerpt available for this source.</p>
          )}

          {/* Relevance score */}
          <div className="mt-2 flex items-center gap-1.5 text-[10px] text-ink-muted">
            <span>Relevance</span>
            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-primary-100">
              <div
                className="h-full rounded-full bg-primary-400"
                style={{ width: `${Math.round(chunk.relevance_score * 100)}%` }}
              />
            </div>
            <span>{Math.round(chunk.relevance_score * 100)}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main ChatPanel ────────────────────────────────────────────────────────────

export default function ChatPanel({ sessionId }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState<string>('')
  const [streaming, setStreaming] = useState<boolean>(false)
  // expandedCitations: Map keyed by message index → Set of expanded citation indices
  const [expandedCitations, setExpandedCitations] = useState<Map<number, Set<number>>>(
    new Map()
  )
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupRef.current?.()
    }
  }, [])

  function toggleCitation(messageIdx: number, citationIdx: number) {
    setExpandedCitations((prev) => {
      const next = new Map(prev)
      const set = new Set(next.get(messageIdx) ?? [])
      if (set.has(citationIdx)) {
        set.delete(citationIdx)
      } else {
        set.add(citationIdx)
      }
      next.set(messageIdx, set)
      return next
    })
  }

  function handleSend() {
    const messageText = inputValue.trim()
    if (!messageText || streaming) return

    setInputValue('')
    setStreaming(true)

    // Append user message + placeholder assistant message
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: messageText },
      { role: 'assistant', content: '', streaming: true },
    ])

    const cleanup = streamChat(
      sessionId,
      messageText,
      // onToken: append token to last message
      (token: string) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, content: last.content + token }
          }
          return updated
        })
      },
      // onCitations
      (chunks: RetrievedChunk[]) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, citations: chunks }
          }
          return updated
        })
      },
      // onDone
      () => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, streaming: false }
          }
          return updated
        })
        setStreaming(false)
      },
      // onError
      (msg: string) => {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: `[Error: ${msg}]`,
              streaming: false,
            }
          }
          return updated
        })
        setStreaming(false)
      }
    )

    cleanupRef.current = cleanup
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      handleSend()
    }
  }

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Messages list */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <p className="mt-6 text-center text-sm text-ink-muted">
            Ask a question about your study material.
          </p>
        )}

        {messages.map((message, msgIdx) => (
          <div
            key={msgIdx}
            className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Bubble */}
            <div
              className={
                message.role === 'user'
                  ? 'max-w-[85%] rounded-xl bg-primary-600 px-3.5 py-2.5 text-sm text-white shadow-soft'
                  : 'max-w-[85%] rounded-xl border border-surface-border bg-surface-subtle px-3.5 py-2.5 text-sm text-ink-soft shadow-soft'
              }
            >
              {message.content}
              {message.role === 'assistant' && message.streaming && (
                <span className="ml-1 animate-pulse text-ink-muted">▋</span>
              )}
            </div>

            {/* Citation chips — shown below completed assistant messages */}
            {message.role === 'assistant' &&
              !message.streaming &&
              message.citations &&
              message.citations.length > 0 && (
                <div className="mt-2 flex max-w-[90%] flex-col gap-1.5">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                    Sources
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {message.citations.map((chunk, citIdx) => (
                      <CitationChip
                        key={citIdx}
                        chunk={chunk}
                        expanded={expandedCitations.get(msgIdx)?.has(citIdx) ?? false}
                        onToggle={() => toggleCitation(msgIdx, citIdx)}
                      />
                    ))}
                  </div>
                </div>
              )}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="flex shrink-0 gap-2 border-t border-surface-border pt-3">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          placeholder="Ask a question…"
          className={[
            'flex-1 rounded-xl border border-surface-border bg-surface-subtle px-3.5 py-2 text-sm text-ink-soft',
            'placeholder:text-ink-muted',
            'focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-400/30',
            'disabled:cursor-not-allowed disabled:opacity-50',
          ].join(' ')}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={streaming || !inputValue.trim()}
          className={[
            'inline-flex shrink-0 items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition-all',
            'bg-primary-600 text-white shadow-soft hover:bg-primary-700 active:bg-primary-700',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
          ].join(' ')}
        >
          {streaming ? (
            <svg
              aria-hidden
              className="h-4 w-4 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z"
              />
            </svg>
          ) : (
            <svg
              aria-hidden
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="h-4 w-4"
            >
              <path d="M2.87 2.298a.75.75 0 0 0-.812.21.75.75 0 0 0-.1.786l1.83 4.614a.75.75 0 0 0 .526.456l4.74 1.186-4.74 1.186a.75.75 0 0 0-.526.456L1.958 15.7a.75.75 0 0 0 .912.985l12-5.25a.75.75 0 0 0 0-1.37l-12-5.25a.75.75 0 0 0-.001 0Z" />
            </svg>
          )}
          <span className="sr-only">Send</span>
        </button>
      </div>
    </div>
  )
}
