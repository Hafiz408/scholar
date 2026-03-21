'use client'

import { useEffect, useRef, useState } from 'react'
import { streamSuperChat } from '@/lib/sse'
import { listSources } from '@/lib/api'
import type { ChatMessage } from '@/types'

export default function SuperPage() {
  const [threadId] = useState<string>(() => {
    if (typeof window === 'undefined') return ''
    const stored = localStorage.getItem('scholar_super_thread_id')
    if (stored) return stored
    const id = crypto.randomUUID()
    localStorage.setItem('scholar_super_thread_id', id)
    return id
  })

  const [readySourceCount, setReadySourceCount] = useState<number>(0)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState<boolean>(false)
  const cancelRef = useRef<(() => void) | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch ready source count on mount
  useEffect(() => {
    listSources()
      .then((sources) => {
        const count = sources.filter((s) => s.status === 'ready').length
        setReadySourceCount(count)
      })
      .catch(() => {})
  }, [])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Cleanup SSE stream on unmount
  useEffect(() => {
    return () => {
      cancelRef.current?.()
    }
  }, [])

  function handleSend() {
    const msg = input.trim()
    if (!msg || isStreaming) return
    setInput('')
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: msg, citations: [] },
      { role: 'assistant', content: '', citations: [] },
    ])
    setIsStreaming(true)

    const cancel = streamSuperChat(
      msg,
      threadId,
      (token) =>
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: updated[updated.length - 1].content + token,
          }
          return updated
        }),
      (chunks) =>
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            citations: chunks,
          }
          return updated
        }),
      () => setIsStreaming(false),
      (errMsg) => {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: ${errMsg}`,
          }
          return updated
        })
        setIsStreaming(false)
      }
    )
    cancelRef.current = cancel
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="px-6 py-3 border-b bg-white flex items-center justify-between flex-shrink-0">
        <h1 className="font-semibold text-lg text-gray-900">Super Agent</h1>
        <span className="text-sm text-gray-500">
          {readySourceCount} source{readySourceCount !== 1 ? 's' : ''} indexed
        </span>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <p className="text-center text-gray-400 text-sm mt-8">
            Ask anything across all your indexed books.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-lg rounded-lg px-4 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border text-gray-800'
              }`}
            >
              {msg.content || (isStreaming && i === messages.length - 1 ? '...' : '')}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t bg-white px-4 py-3 flex gap-2 flex-shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="Ask across all your books..."
          disabled={isStreaming}
          className="flex-1 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isStreaming ? '...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
