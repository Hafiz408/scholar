'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { generateQuiz, submitQuiz } from '@/lib/api'
import type { QuizQuestion, QuizResult, StudySession } from '@/types'

type QuizPhase = 'idle' | 'generating' | 'active' | 'results'

interface QuizPanelProps {
  sessionId: string
  goalId: string
  onFollowupAdded?: (session: StudySession | null) => void
}

export default function QuizPanel({ sessionId, goalId, onFollowupAdded }: QuizPanelProps) {
  const router = useRouter()
  const [phase, setPhase] = useState<QuizPhase>('idle')
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  // selectedAnswers: keyed by question index, value is the selected option index
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({})
  const [result, setResult] = useState<QuizResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleStartQuiz() {
    setPhase('generating')
    setError(null)
    try {
      const qs = await generateQuiz(sessionId)
      setQuestions(qs)
      setPhase('active')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate quiz')
      setPhase('idle')
    }
  }

  async function handleSubmit() {
    if (submitting || !allAnswered) return
    setSubmitting(true)
    setError(null)
    // Build answers map: question_id -> selected option index
    const answers: Record<string, number> = {}
    questions.forEach((q, i) => {
      answers[q.id] = selectedAnswers[i]
    })
    try {
      const quizResult = await submitQuiz(sessionId, { answers })
      setResult(quizResult)
      setPhase('results')
      if (quizResult.followup_session_added && onFollowupAdded) {
        onFollowupAdded(quizResult.followup_session ?? null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit quiz')
    } finally {
      setSubmitting(false)
    }
  }

  function handleTryAgain() {
    setError(null)
    setPhase('idle')
    setQuestions([])
    setSelectedAnswers({})
    setResult(null)
  }

  const allAnswered =
    questions.length > 0 && Object.keys(selectedAnswers).length === questions.length

  const scorePercent = result ? Math.round(result.score * 100) : 0
  const scoreColor =
    scorePercent >= 70
      ? 'text-green-600'
      : scorePercent >= 50
      ? 'text-yellow-500'
      : 'text-red-600'

  return (
    <div className="h-full flex flex-col">
      {phase === 'idle' && (
        <div className="flex flex-col items-center justify-center h-full gap-4">
          <p className="text-gray-600 text-sm text-center">
            Ready to test your knowledge? Start a quiz based on this session.
          </p>
          <button
            onClick={handleStartQuiz}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Start Quiz
          </button>
        </div>
      )}

      {phase === 'generating' && (
        <div className="flex flex-col items-center justify-center h-full gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          <p className="text-gray-500 text-sm">Generating quiz questions...</p>
        </div>
      )}

      {phase === 'active' && (
        <div className="flex flex-col h-full">
          <div className="flex-1 overflow-y-auto space-y-6 pb-4">
            {questions.map((q, i) => (
              <div key={q.id} className="space-y-2">
                <p className="font-medium text-sm">
                  {i + 1}. {q.question}
                </p>
                <div className="space-y-2">
                  {q.options.map((option, optIdx) => (
                    <label key={optIdx} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name={`q-${i}`}
                        value={optIdx}
                        checked={selectedAnswers[i] === optIdx}
                        onChange={() =>
                          setSelectedAnswers((prev) => ({ ...prev, [i]: optIdx }))
                        }
                        className="accent-blue-600"
                      />
                      <span className="text-sm">{option}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || submitting}
            className="mt-2 w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Submitting...' : 'Submit Quiz'}
          </button>
        </div>
      )}

      {phase === 'results' && result && (
        <div className="space-y-4 overflow-y-auto">
          <div className="text-center py-4">
            <p className={`text-4xl font-bold ${scoreColor}`}>{scorePercent}%</p>
            <p className="text-gray-500 text-sm mt-1">
              {result.correct_count} of {result.total_questions} correct
            </p>
          </div>

          <div className="space-y-4">
            {questions.map((q, i) => {
              const qResult = result.per_question.find((r) => r.question_id === q.id)
              const isCorrect = qResult?.correct ?? false
              const selectedIdx = selectedAnswers[i]
              const selectedOption = q.options[selectedIdx] ?? '(no answer)'

              return (
                <div
                  key={q.id}
                  className={`border-l-4 pl-3 ${isCorrect ? 'border-green-500' : 'border-red-500'}`}
                >
                  <p className="font-medium text-sm">{q.question}</p>
                  <p
                    className={`text-sm mt-1 ${isCorrect ? 'text-green-600' : 'text-red-600'}`}
                  >
                    Your answer: {selectedOption}
                  </p>
                  {qResult?.explanation && (
                    <p className="text-xs text-gray-500 italic mt-1">{qResult.explanation}</p>
                  )}
                </div>
              )
            })}
          </div>

          <button
            onClick={() => router.push('/goals/' + goalId)}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors mt-4"
          >
            Complete Session
          </button>
        </div>
      )}

      {error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm">
          <p className="text-red-600">{error}</p>
          <button
            onClick={handleTryAgain}
            className="text-red-500 underline text-xs mt-1 hover:text-red-700"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  )
}
