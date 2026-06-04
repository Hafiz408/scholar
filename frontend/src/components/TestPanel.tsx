'use client'

import { useState } from 'react'
import { generateFinalTest, submitFinalTest } from '@/lib/api'
import type { TestQuestion, TestResult } from '@/types'

type TestPhase = 'idle' | 'generating' | 'active' | 'results'

const CONFETTI_COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#a855f7','#ec4899']

export default function TestPanel({ goalId }: { goalId: string }) {
  const [phase, setPhase] = useState<TestPhase>('idle')
  const [questions, setQuestions] = useState<TestQuestion[]>([])
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({})
  const [result, setResult] = useState<TestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showConfetti, setShowConfetti] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleGenerate() {
    setPhase('generating')
    setError(null)
    try {
      const qs = await generateFinalTest(goalId)
      setQuestions(qs)
      setPhase('active')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate test')
      setPhase('idle')
    }
  }

  async function handleSubmit() {
    if (submitting || !allAnswered) return
    setSubmitting(true)
    setError(null)
    const answers: Record<string, number> = {}
    questions.forEach((q, i) => { answers[q.id] = selectedAnswers[i] })
    try {
      const testResult = await submitFinalTest(goalId, answers)
      setResult(testResult)
      setPhase('results')
      if (testResult.goal_complete) {
        setShowConfetti(true)
        setTimeout(() => setShowConfetti(false), 3500)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit test')
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered = questions.length > 0 && Object.keys(selectedAnswers).length === questions.length
  const scorePercent = result ? Math.round(result.score * 100) : 0
  const scoreColor = scorePercent >= 70 ? 'text-green-600' : scorePercent >= 50 ? 'text-yellow-500' : 'text-red-600'

  return (
    <div className="mt-8 border rounded-lg p-6 bg-white">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">Final Test</h2>

      {showConfetti && (
        <div className="confetti-container" aria-hidden="true">
          {Array.from({ length: 20 }).map((_, i) => (
            <span
              key={i}
              className="confetti-piece"
              style={{
                left: `${Math.random() * 100}%`,
                backgroundColor: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
                animationDelay: `${Math.random() * 0.5}s`,
              }}
            />
          ))}
        </div>
      )}

      {phase === 'idle' && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-gray-600 text-sm">All sessions complete. Take the cumulative final test to mark this goal complete.</p>
          <button onClick={handleGenerate} className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors text-sm">
            Take Final Test
          </button>
        </div>
      )}

      {phase === 'generating' && (
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600" />
          <p className="text-gray-500 text-sm">Generating test questions...</p>
        </div>
      )}

      {phase === 'active' && (
        <div className="space-y-6">
          {questions.map((q, i) => (
            <div key={q.id} className="space-y-2">
              <p className="font-medium text-sm text-gray-800">{i + 1}. {q.question} <span className="text-xs text-gray-400">(Session {q.session_number})</span></p>
              <div className="space-y-1">
                {q.options.map((opt, optIdx) => (
                  <label key={optIdx} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name={`tq-${i}`} value={optIdx}
                      checked={selectedAnswers[i] === optIdx}
                      onChange={() => setSelectedAnswers(prev => ({ ...prev, [i]: optIdx }))}
                      className="accent-indigo-600"
                    />
                    <span className="text-sm">{opt}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button onClick={handleSubmit} disabled={!allAnswered || submitting}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed">
            {submitting ? 'Submitting...' : 'Submit Test'}
          </button>
        </div>
      )}

      {phase === 'results' && result && (
        <div className="space-y-4">
          {result.goal_complete && (
            <div className="bg-green-50 border border-green-300 rounded-lg px-4 py-3 text-green-800 font-semibold">
              Goal Complete!
            </div>
          )}
          <div className="text-center py-2">
            <p className={`text-4xl font-bold ${scoreColor}`}>{scorePercent}%</p>
            <p className="text-gray-500 text-sm mt-1">{result.correct_count} of {result.total_questions} correct</p>
          </div>
          {result.weak_session_numbers.length > 0 && (
            <p className="text-sm text-gray-600">
              Weak sessions: {result.weak_session_numbers.join(', ')} &mdash; consider reviewing these.
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">{error}</div>
      )}
    </div>
  )
}
