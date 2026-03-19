'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { listSources, createGoal } from '@/lib/api'
import type { KnowledgeSource } from '@/types'

export default function GoalForm() {
  const router = useRouter()

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([])
  const [deadlineDays, setDeadlineDays] = useState<number>(30)
  const [level, setLevel] = useState<string>('beginner')
  const [sessionsPerWeek, setSessionsPerWeek] = useState<number>(3)
  const [sources, setSources] = useState<KnowledgeSource[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSources()
      .then(setSources)
      .catch(() => {
        // Non-fatal: form still works without source list
        setSources([])
      })
  }, [])

  function toggleSource(id: string) {
    setSelectedSourceIds(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const studyPlan = await createGoal({
        title,
        topic,
        source_ids: selectedSourceIds,
        deadline_days: deadlineDays,
        level,
        sessions_per_week: sessionsPerWeek,
      })
      router.push(`/goals/${studyPlan.goal.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create goal')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
      {error && (
        <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Goal Title
        </label>
        <input
          type="text"
          required
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="e.g. Master Cell Biology"
          className="border rounded p-2 w-full"
        />
      </div>

      {/* Topic */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Study Topic
        </label>
        <input
          type="text"
          required
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="e.g. Cell Structure and Function"
          className="border rounded p-2 w-full"
        />
      </div>

      {/* Knowledge Sources multi-select (checkbox list) */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Knowledge Sources
        </label>
        {sources.length === 0 ? (
          <p className="text-sm text-gray-500">
            No sources available. Upload sources on the Knowledge Base page first.
          </p>
        ) : (
          <div className="border rounded p-2 space-y-2 max-h-40 overflow-y-auto">
            {sources.map(source => (
              <label key={source.id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  value={source.id}
                  checked={selectedSourceIds.includes(source.id)}
                  onChange={() => toggleSource(source.id)}
                />
                <span className="text-sm">{source.title}</span>
                <span className="text-xs text-gray-400">({source.source_type})</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Deadline */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Deadline
        </label>
        <select
          value={deadlineDays}
          onChange={e => setDeadlineDays(Number(e.target.value))}
          className="border rounded p-2 w-full"
        >
          <option value={7}>7 days</option>
          <option value={14}>14 days</option>
          <option value={21}>21 days</option>
          <option value={30}>30 days</option>
          <option value={60}>60 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      {/* Level */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Study Level
        </label>
        <div className="flex gap-4">
          {(['beginner', 'intermediate', 'advanced'] as const).map(l => (
            <label key={l} className="flex items-center gap-1 cursor-pointer">
              <input
                type="radio"
                name="level"
                value={l}
                checked={level === l}
                onChange={() => setLevel(l)}
              />
              <span className="text-sm capitalize">{l}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Sessions per week */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Sessions per Week
        </label>
        <input
          type="number"
          min={1}
          max={7}
          value={sessionsPerWeek}
          onChange={e => setSessionsPerWeek(Number(e.target.value))}
          className="border rounded p-2 w-full"
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {submitting ? 'Creating...' : 'Create Goal'}
      </button>
    </form>
  )
}
