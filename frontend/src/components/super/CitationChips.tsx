import type { RetrievedChunk } from '@/types'

interface CitationChipsProps {
  citations: RetrievedChunk[]
}

/**
 * Renders a row of compact citation chips beneath an assistant message.
 * Each chip shows source_title and page_number (when present).
 */
export default function CitationChips({ citations }: CitationChipsProps) {
  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Citations">
      {citations.map((chunk, i) => (
        <span
          key={`${chunk.source_id}-${chunk.page_number ?? i}`}
          title={chunk.section_title ?? chunk.source_title}
          className="inline-flex items-center gap-1 rounded-full border border-surface-border bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700 ring-1 ring-inset ring-primary-200/60"
        >
          <span className="max-w-[140px] truncate">{chunk.source_title}</span>
          {chunk.page_number != null && (
            <span className="text-primary-500">p.{chunk.page_number}</span>
          )}
        </span>
      ))}
    </div>
  )
}
