import type {
  KnowledgeSource,
  StudyPlan,
  StudySession,
  RetrievedChunk,
  QuizQuestion,
  QuizResult,
  TestQuestion,
  TestResult,
} from '@/types'
import { logger } from './logger'

const API_BASE = '/api'

// ─── Request types ──────────────────────────────────────────────────────────

export interface CreateGoalRequest {
  title: string
  topic: string
  level: string
  deadline_days: number
  sessions_per_week: number
  source_ids: string[]
}

// POST /goals returns a creation acknowledgement (not the full plan).
// The full StudyPlan is fetched separately via getGoalPlan(goal_id).
export interface CreateGoalResponse {
  goal_id: string
  session_count: number
  rationale: string
}

export interface QuizSubmissionRequest {
  answers: Record<string, number> // question_id -> selected_index (0-3)
}

export interface IngestionStatus {
  source_id: string
  status: string
}

// ─── Error handling ───────────────────────────────────────────────────────────

/**
 * Thrown by every API call in this module on a non-OK response or a network
 * failure. Carries the HTTP status, the backend-provided detail (when present),
 * and the request context so callers can render meaningful messages.
 *
 * status === 0 indicates the request never reached the server (e.g. network
 * down, DNS failure, CORS) — fetch itself threw.
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail?: string
  readonly method: string
  readonly path: string

  constructor(args: {
    status: number
    detail?: string
    method: string
    path: string
  }) {
    const { status, detail, method, path } = args
    const reason = detail ?? (status === 0 ? 'network error' : `HTTP ${status}`)
    super(`${method} ${path} failed: ${reason}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.method = method
    this.path = path
  }
}

/**
 * Extracts a human-readable detail from a non-OK response body, handling:
 *   - the app's handled-error shape:    { "error": { "status", "detail" } }
 *   - FastAPI's default shape:          { "detail": ... }  (string or array)
 *   - anything else:                    raw text, or statusText as a fallback
 */
async function extractDetail(res: Response): Promise<string | undefined> {
  let raw: string
  try {
    raw = await res.text()
  } catch {
    return res.statusText || undefined
  }
  if (!raw) return res.statusText || undefined

  try {
    const body = JSON.parse(raw) as unknown
    if (body && typeof body === 'object') {
      const obj = body as Record<string, unknown>

      // App handled-error shape: { error: { status, detail } }
      if (obj.error && typeof obj.error === 'object') {
        const err = obj.error as Record<string, unknown>
        if (typeof err.detail === 'string') return err.detail
      }

      // FastAPI default shape: { detail: string | array | object }
      if (typeof obj.detail === 'string') return obj.detail
      if (Array.isArray(obj.detail)) {
        // Validation errors: [{ loc, msg, type }, ...]
        return obj.detail
          .map((d) => {
            if (d && typeof d === 'object' && 'msg' in (d as object)) {
              return String((d as Record<string, unknown>).msg)
            }
            return JSON.stringify(d)
          })
          .join('; ')
      }
      if (obj.detail !== undefined) return JSON.stringify(obj.detail)
    }
    // Valid JSON but no recognizable detail field — surface the raw JSON.
    return raw
  } catch {
    // Not JSON — surface the raw text, falling back to statusText.
    return raw || res.statusText || undefined
  }
}

/**
 * Core request helper. Every exported call delegates here so error parsing and
 * logging live in one place.
 *
 * - On a non-OK response: parses the body for a backend detail, logs, and
 *   throws ApiError.
 * - On a network failure (fetch throws): logs and re-throws as ApiError with
 *   status 0.
 * - On success: returns parsed JSON, or undefined for 204 / when
 *   opts.parseJson === false.
 */
async function request<T>(
  path: string,
  init?: RequestInit,
  opts?: { parseJson?: boolean }
): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const parseJson = opts?.parseJson ?? true

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch (err) {
    logger.error(`[api] ${method} ${path} — network error`, err)
    throw new ApiError({
      status: 0,
      detail: err instanceof Error ? err.message : 'network request failed',
      method,
      path,
    })
  }

  if (!res.ok) {
    const detail = await extractDetail(res)
    logger.error(`[api] ${method} ${path} — ${res.status}`, detail)
    throw new ApiError({ status: res.status, detail, method, path })
  }

  if (!parseJson || res.status === 204) {
    return undefined as T
  }

  return (await res.json()) as T
}

// ─── Knowledge endpoints ─────────────────────────────────────────────────────

export async function listSources(): Promise<KnowledgeSource[]> {
  return request<KnowledgeSource[]>('/knowledge')
}

export async function uploadSource(
  formData: FormData
): Promise<{ source_id: string; status: string }> {
  // Do NOT set Content-Type — browser sets multipart boundary automatically
  return request<{ source_id: string; status: string }>('/knowledge/upload', {
    method: 'POST',
    body: formData,
  })
}

export async function getSourceStatus(sourceId: string): Promise<IngestionStatus> {
  return request<IngestionStatus>(`/knowledge/${sourceId}/status`)
}

export async function deleteSource(sourceId: string): Promise<void> {
  // Accept 204 as success; 404 is also treated as success (already deleted)
  let res: Response
  try {
    res = await fetch(`${API_BASE}/knowledge/${sourceId}`, { method: 'DELETE' })
  } catch (err) {
    logger.error(`[api] DELETE /knowledge/${sourceId} — network error`, err)
    throw new ApiError({
      status: 0,
      detail: err instanceof Error ? err.message : 'network request failed',
      method: 'DELETE',
      path: `/knowledge/${sourceId}`,
    })
  }

  if (res.ok || res.status === 204 || res.status === 404) return

  const detail = await extractDetail(res)
  logger.error(`[api] DELETE /knowledge/${sourceId} — ${res.status}`, detail)
  throw new ApiError({
    status: res.status,
    detail,
    method: 'DELETE',
    path: `/knowledge/${sourceId}`,
  })
}

// ─── Goals endpoints ─────────────────────────────────────────────────────────

export async function createGoal(data: CreateGoalRequest): Promise<CreateGoalResponse> {
  return request<CreateGoalResponse>('/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function getGoalPlan(goalId: string): Promise<StudyPlan> {
  return request<StudyPlan>(`/goals/${goalId}`)
}

// ─── Sessions endpoints ───────────────────────────────────────────────────────

/**
 * Returns the URL for the SSE session-start endpoint.
 * Used by sse.ts to construct the fetchEventSource request.
 */
export function startSession(sessionId: string): string {
  return `${API_BASE}/sessions/${sessionId}/start`
}

export async function getSession(sessionId: string): Promise<StudySession> {
  return request<StudySession>(`/sessions/${sessionId}`)
}

/**
 * Initiates a POST to the chat SSE endpoint and returns the raw Response.
 * sse.ts streamChat uses this to process token/citations/done events.
 * parseJson:false routes through the shared error handling but hands back the
 * untouched Response for the SSE consumer to stream.
 */
export async function sendChatMessage(
  sessionId: string,
  message: string
): Promise<Response> {
  const path = `/sessions/${sessionId}/chat`
  const method = 'POST'

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
  } catch (err) {
    logger.error(`[api] ${method} ${path} — network error`, err)
    throw new ApiError({
      status: 0,
      detail: err instanceof Error ? err.message : 'network request failed',
      method,
      path,
    })
  }

  if (!res.ok) {
    const detail = await extractDetail(res)
    logger.error(`[api] ${method} ${path} — ${res.status}`, detail)
    throw new ApiError({ status: res.status, detail, method, path })
  }

  return res
}

// ─── Quiz endpoints ───────────────────────────────────────────────────────────

export async function generateQuiz(sessionId: string): Promise<QuizQuestion[]> {
  return request<QuizQuestion[]>(`/sessions/${sessionId}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export async function submitQuiz(
  sessionId: string,
  submission: QuizSubmissionRequest
): Promise<QuizResult> {
  return request<QuizResult>(`/sessions/${sessionId}/quiz/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(submission),
  })
}

// ─── Final test endpoints ─────────────────────────────────────────────────────

export async function generateFinalTest(goalId: string): Promise<TestQuestion[]> {
  return request<TestQuestion[]>(`/goals/${goalId}/test/generate`, { method: 'POST' })
}

export async function submitFinalTest(
  goalId: string,
  answers: Record<string, number>
): Promise<TestResult> {
  return request<TestResult>(`/goals/${goalId}/test/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
}

// ─── Notion export endpoint ───────────────────────────────────────────────────

export async function exportToNotion(goalId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/goals/${goalId}/export/notion`, { method: 'POST' })
}

// Re-export types used by other modules
export type { KnowledgeSource, StudyPlan, StudySession, RetrievedChunk, QuizQuestion, QuizResult, TestQuestion, TestResult }
