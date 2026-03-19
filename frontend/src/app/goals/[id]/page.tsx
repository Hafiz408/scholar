'use client'

import { useState, useEffect } from 'react'
import { getGoalPlan } from '@/lib/api'
import ProgressBar from '@/components/ProgressBar'
import StudyPlan from '@/components/StudyPlan'
import type { StudyPlan as StudyPlanType } from '@/types'

export default function GoalDetailPage({ params }: { params: { id: string } }) {
  const goalId = params.id

  const [plan, setPlan] = useState<StudyPlanType | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getGoalPlan(goalId)
      .then(setPlan)
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load goal')
      })
  }, [goalId])

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    )
  }

  if (!plan) {
    return (
      <div className="p-8 text-gray-500">Loading goal...</div>
    )
  }

  const completed = plan.sessions.filter(s => s.status === 'complete').length
  const total = plan.sessions.length

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">{plan.goal.title}</h1>
      <p className="text-gray-600 mt-1">{plan.goal.topic}</p>

      <div className="mt-6">
        <ProgressBar completed={completed} total={total} />
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Study Sessions</h2>
        <StudyPlan sessions={plan.sessions} />
      </div>
    </div>
  )
}
