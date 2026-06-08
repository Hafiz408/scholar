'use client'

import { useState, useEffect } from 'react'

const STORAGE_KEY = 'scholar_home_intro_dismissed'

/**
 * Dismissible newcomer banner. Reads dismissal state from localStorage on mount;
 * once dismissed, hides immediately and persists across page loads.
 */
export default function IntroBanner() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    try {
      const dismissed = localStorage.getItem(STORAGE_KEY)
      if (!dismissed) setVisible(true)
    } catch {
      // localStorage unavailable (SSR guard, private browsing, etc.)
    }
  }, [])

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, '1')
    } catch {
      // ignore
    }
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div
      role="banner"
      className="relative mb-8 overflow-hidden rounded-2xl border border-primary-200 bg-primary-50 px-6 py-5 shadow-soft"
    >
      {/* Subtle decorative blob */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-primary-100 opacity-50"
      />

      <div className="relative flex items-start justify-between gap-4">
        <div className="max-w-2xl">
          <h2 className="font-serif text-xl font-semibold text-ink">
            Scholar turns your books into adaptive, guided study plans.
          </h2>
          <p className="mt-1.5 text-sm text-ink-soft">
            Upload a PDF or URL, set a learning goal, and Scholar will generate
            a personalised session plan — with quizzes, notes, and a Super Agent
            ready to answer any question.
          </p>
        </div>

        <button
          onClick={dismiss}
          aria-label="Dismiss introduction banner"
          className="shrink-0 rounded-xl p-1.5 text-ink-muted transition-colors hover:bg-primary-100 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <button
        onClick={dismiss}
        className="mt-3 text-xs font-medium text-primary-600 transition-colors hover:text-primary-700 focus:outline-none focus-visible:underline"
      >
        Got it, let me start →
      </button>
    </div>
  )
}
