'use client'

import { useState, useEffect } from 'react'
import { exportToNotion, getGoalPlan } from '@/lib/api'

interface NotionExportButtonProps {
  goalId: string
  initialNotionUrl?: string | null
}

export default function NotionExportButton({ goalId, initialNotionUrl }: NotionExportButtonProps) {
  type ExportState = 'idle' | 'exporting' | 'polling' | 'done' | 'error'
  const [state, setState] = useState<ExportState>(initialNotionUrl ? 'done' : 'idle')
  const [notionUrl, setNotionUrl] = useState<string | null>(initialNotionUrl ?? null)
  const [polling, setPolling] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Polling effect — runs when polling=true
  useEffect(() => {
    if (!polling) return
    const interval = setInterval(async () => {
      try {
        const plan = await getGoalPlan(goalId)
        if (plan.goal.notion_page_url) {
          setNotionUrl(plan.goal.notion_page_url)
          setPolling(false)
          setState('done')
        }
      } catch { /* non-fatal — keep polling */ }
    }, 3000)
    return () => clearInterval(interval)
  }, [polling, goalId])

  async function handleExport() {
    setState('exporting')
    setErrorMsg(null)
    try {
      await exportToNotion(goalId)
      setState('polling')
      setPolling(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed'
      // 400 = Notion not configured on this server
      if (msg.includes('400')) {
        setErrorMsg('Notion export is not configured on this server. Set notion_api_key and notion_parent_page_id in backend config.')
      } else {
        setErrorMsg(msg)
      }
      setState('error')
    }
  }

  if (state === 'done' && notionUrl) {
    return (
      <a href={notionUrl} target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-700 transition-colors">
        View in Notion
      </a>
    )
  }

  if (state === 'polling') {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600" />
        Syncing with Notion...
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleExport}
        disabled={state === 'exporting'}
        className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {state === 'exporting' ? 'Exporting...' : 'Export to Notion'}
      </button>
      {state === 'error' && errorMsg && (
        <p className="text-xs text-red-600">{errorMsg}</p>
      )}
    </div>
  )
}
