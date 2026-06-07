import type { ChatMessage } from '@/types'
import CitationChips from './CitationChips'

interface MessageBubbleProps {
  message: ChatMessage
  isStreaming?: boolean
}

/**
 * A single chat message bubble.
 * User messages: right-aligned, primary bg.
 * Assistant messages: left-aligned, card bg, with optional citation chips.
 */
export default function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={[
          'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-soft',
          isUser
            ? 'bg-primary-600 text-white'
            : 'border border-surface-border bg-surface-card text-ink-soft',
        ].join(' ')}
      >
        {message.content || (isStreaming ? '' : '')}
        {isStreaming && (
          <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-current opacity-70" aria-hidden />
        )}
      </div>

      {/* Citation chips — only on completed assistant messages */}
      {!isUser && !isStreaming && message.citations && message.citations.length > 0 && (
        <div className="mt-1.5 max-w-[80%]">
          <CitationChips citations={message.citations} />
        </div>
      )}
    </div>
  )
}
