'use client'

import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  listSources,
  uploadSource,
  getSourceStatus,
  deleteSource,
} from '@/lib/api'
import type { KnowledgeSource, IngestionStatus } from '@/types'

// ─── StatusPill ──────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  indexing_pageindex: 'bg-blue-100 text-blue-600',
  indexing_vectors: 'bg-yellow-100 text-yellow-600',
  ready: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-600',
}

function StatusPill({ status }: { status: IngestionStatus }) {
  const colorClass = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

// ─── KnowledgeUpload ─────────────────────────────────────────────────────────

export default function KnowledgeUpload() {
  const [sources, setSources] = useState<KnowledgeSource[]>([])
  const [pendingSourceIds, setPendingSourceIds] = useState<string[]>([])
  const [urlInput, setUrlInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load sources on mount
  useEffect(() => {
    listSources()
      .then((data) => {
        setSources(data)
        const pending = data
          .filter((s) => s.status !== 'ready' && s.status !== 'failed')
          .map((s) => s.id)
        setPendingSourceIds(pending)
      })
      .catch((err) => setError(String(err)))
  }, [])

  // Poll pending sources every 3000ms
  useEffect(() => {
    if (!pendingSourceIds.length) return

    const interval = setInterval(async () => {
      try {
        const updates = await Promise.all(
          pendingSourceIds.map((id) => getSourceStatus(id))
        )
        setSources((prev) =>
          prev.map((s) => {
            const update = updates.find((u) => u.source_id === s.id)
            return update ? { ...s, status: update.status as IngestionStatus } : s
          })
        )
        setPendingSourceIds((prev) =>
          prev.filter((id) => {
            const s = updates.find((u) => u.source_id === id)
            return s && s.status !== 'ready' && s.status !== 'failed'
          })
        )
      } catch {
        // Polling errors are non-fatal — keep retrying
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [pendingSourceIds])

  // Handle file drop
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!acceptedFiles.length) return
      setUploading(true)
      setError(null)
      try {
        const formData = new FormData()
        formData.append('file', acceptedFiles[0])
        // Do NOT set Content-Type — browser sets multipart boundary automatically
        const result = await uploadSource(formData)
        setPendingSourceIds((prev) =>
          prev.includes(result.source_id) ? prev : [...prev, result.source_id]
        )
        setSources((prev) =>
          prev.some((s) => s.id === result.source_id)
            ? prev
            : [
                ...prev,
                {
                  id: result.source_id,
                  title: acceptedFiles[0].name,
                  source_type: 'pdf',
                  page_count: 0,
                  status: 'pending',
                  created_at: new Date().toISOString(),
                } as KnowledgeSource,
              ]
        )
      } catch (err) {
        setError(`Upload failed: ${String(err)}`)
      } finally {
        setUploading(false)
      }
    },
    []
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
    onDrop,
    onDropRejected: (rejections) => {
      const reason = rejections[0]?.errors[0]?.message ?? 'File rejected'
      setError(`Upload rejected: ${reason} (PDF only, up to 50 MB)`)
    },
  })

  // Handle URL submit
  async function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!urlInput.trim()) return
    setUploading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('url', urlInput.trim())
      const result = await uploadSource(formData)
      setPendingSourceIds((prev) =>
        prev.includes(result.source_id) ? prev : [...prev, result.source_id]
      )
      setSources((prev) =>
        prev.some((s) => s.id === result.source_id)
          ? prev
          : [
              ...prev,
              {
                id: result.source_id,
                title: urlInput.trim(),
                source_type: 'url',
                url: urlInput.trim(),
                page_count: 0,
                status: 'pending',
                created_at: new Date().toISOString(),
              } as KnowledgeSource,
            ]
      )
      setUrlInput('')
    } catch (err) {
      setError(`URL submit failed: ${String(err)}`)
    } finally {
      setUploading(false)
    }
  }

  // Handle delete
  async function handleDelete(sourceId: string) {
    try {
      await deleteSource(sourceId)
      setSources((prev) => prev.filter((s) => s.id !== sourceId))
      setPendingSourceIds((prev) => prev.filter((id) => id !== sourceId))
    } catch (err) {
      setError(`Delete failed: ${String(err)}`)
    }
  }

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <div className="p-3 rounded-md bg-red-50 text-red-700 text-sm">
          {error}
          <button
            className="ml-2 underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <p className="text-gray-500">Uploading...</p>
        ) : isDragActive ? (
          <p className="text-blue-600 font-medium">Drop the PDF here</p>
        ) : (
          <div>
            <p className="text-gray-600 font-medium">
              Drag and drop a PDF here, or click to select
            </p>
            <p className="text-gray-400 text-sm mt-1">PDF files up to 50 MB</p>
          </div>
        )}
      </div>

      {/* URL field */}
      <form onSubmit={handleUrlSubmit} className="flex gap-2">
        <input
          type="url"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          placeholder="https://example.com/article"
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={uploading}
        />
        <button
          type="submit"
          disabled={uploading || !urlInput.trim()}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add URL
        </button>
      </form>

      {/* Source list */}
      <div className="space-y-2">
        {sources.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">
            No sources yet. Upload a PDF or add a URL above.
          </p>
        ) : (
          sources.map((source) => (
            <div
              key={source.id}
              className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-white"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-sm text-gray-800 truncate max-w-xs">
                  {source.title}
                </span>
                <StatusPill status={source.status} />
              </div>
              <button
                onClick={() => handleDelete(source.id)}
                className="ml-3 text-gray-400 hover:text-red-500 text-sm flex-shrink-0"
                aria-label={`Delete ${source.title}`}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
