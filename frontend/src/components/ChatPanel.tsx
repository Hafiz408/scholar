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

export default function ChatPanel({ sessionId }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState<string>('')
  const [streaming, setStreaming] = useState<boolean>(false)
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

  function handleSend() {
    const messageText = inputValue.trim()
    if (!messageText || streaming) return

    setInputValue('')
    setStreaming(true)

    // Append user message
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
    <div className="flex flex-col h-full gap-2">
      {/* Messages list */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-4">
            Ask a question about your study material.
          </p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={
                message.role === 'user'
                  ? 'bg-blue-600 text-white rounded-lg px-3 py-2 max-w-[85%] text-sm'
                  : 'bg-gray-100 rounded-lg px-3 py-2 max-w-[85%] text-sm'
              }
            >
              {message.content}
              {message.role === 'assistant' && message.streaming && (
                <span className="ml-1 animate-pulse">▋</span>
              )}
            </div>
            {/* Citation chips — shown below completed assistant messages */}
            {message.role === 'assistant' &&
              !message.streaming &&
              message.citations &&
              message.citations.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1 max-w-[85%]">
                  {message.citations.map((chunk, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-gray-200 text-gray-700"
                    >
                      {chunk.source_title} p.{chunk.page_number}
                    </span>
                  ))}
                </div>
              )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          placeholder="Ask a question..."
          className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={streaming || !inputValue.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  )
}
