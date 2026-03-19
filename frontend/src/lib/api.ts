import type {
  KnowledgeSource,
  StudyPlan,
  StudySession,
  RetrievedChunk,
  QuizQuestion,
  QuizResult,
} from '@/types'

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

export interface QuizSubmissionRequest {
  answers: Record<string, number> // question_id -> selected_index (0-3)
}

export interface IngestionStatus {
  source_id: string
  status: string
}

// ─── Knowledge endpoints ─────────────────────────────────────────────────────

export async function listSources(): Promise<KnowledgeSource[]> {
  const res = await fetch(`${API_BASE}/knowledge/`)
  if (!res.ok) throw new Error(`listSources failed: ${res.status}`)
  return res.json()
}

export async function uploadSource(
  formData: FormData
): Promise<{ source_id: string; status: string }> {
  // Do NOT set Content-Type — browser sets multipart boundary automatically
  const res = await fetch(`${API_BASE}/knowledge/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`uploadSource failed: ${res.status}`)
  return res.json()
}

export async function getSourceStatus(sourceId: string): Promise<IngestionStatus> {
  const res = await fetch(`${API_BASE}/knowledge/${sourceId}/status`)
  if (!res.ok) throw new Error(`getSourceStatus failed: ${res.status}`)
  return res.json()
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/knowledge/${sourceId}`, {
    method: 'DELETE',
  })
  // Accept 204 as success; 404 is also treated as success (already deleted)
  if (!res.ok && res.status !== 204) throw new Error(`deleteSource failed: ${res.status}`)
}

// ─── Goals endpoints ─────────────────────────────────────────────────────────

export async function createGoal(data: CreateGoalRequest): Promise<StudyPlan> {
  const res = await fetch(`${API_BASE}/goals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`createGoal failed: ${res.status}`)
  return res.json()
}

export async function getGoalPlan(goalId: string): Promise<StudyPlan> {
  const res = await fetch(`${API_BASE}/goals/${goalId}`)
  if (!res.ok) throw new Error(`getGoalPlan failed: ${res.status}`)
  return res.json()
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
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`)
  if (!res.ok) throw new Error(`getSession failed: ${res.status}`)
  return res.json()
}

/**
 * Initiates a POST to the chat SSE endpoint and returns the raw Response.
 * sse.ts streamChat uses this to process token/citations/done events.
 */
export async function sendChatMessage(
  sessionId: string,
  message: string
): Promise<Response> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error(`sendChatMessage failed: ${res.status}`)
  return res
}

// ─── Quiz endpoints ───────────────────────────────────────────────────────────

export async function generateQuiz(sessionId: string): Promise<QuizQuestion[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`generateQuiz failed: ${res.status}`)
  return res.json()
}

export async function submitQuiz(
  sessionId: string,
  submission: QuizSubmissionRequest
): Promise<QuizResult> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/quiz/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(submission),
  })
  if (!res.ok) throw new Error(`submitQuiz failed: ${res.status}`)
  return res.json()
}

// Re-export types used by other modules
export type { KnowledgeSource, StudyPlan, StudySession, RetrievedChunk, QuizQuestion, QuizResult }
