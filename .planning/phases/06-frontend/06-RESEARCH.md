# Phase 6: Frontend - Research

**Researched:** 2026-03-19
**Domain:** Next.js 14 App Router, SSE streaming, react-dropzone, react-markdown, Tailwind CSS
**Confidence:** HIGH (stack is locked by Phase 1 decisions and PRD; SSE patterns verified via official docs and multiple sources)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FE-01 | Knowledge base page: drag-and-drop PDF upload + URL field, source list with status pills, polling during ingestion | react-dropzone `useDropzone` hook + `setInterval`/`useEffect` polling pattern at 3s interval against `GET /knowledge/{id}/status` |
| FE-02 | Goal creation form: title, topic, source multi-select, deadline dropdown, level radio, sessions/week selector | Controlled form with `useState`, multi-select via checkbox list of `KnowledgeSource[]`, POST to `/goals` |
| FE-03 | Goal detail page: progress bar, session card list with locked/available/in-progress/complete states and quiz score badges | `GET /goals/{id}` returns `StudyPlan`, derive progress from `completed_sessions/total_sessions`, session card state from `session.status` |
| FE-04 | Study session page: three-panel layout — Notes (react-markdown with citations), Chat (SSE streaming + citation chips), Quiz (MCQ → results → Complete Session) | Three-column Tailwind grid, `ReactMarkdown` with `remarkPlugins={[remarkGfm]}`, `EventSource` for notes stream + fetch+ReadableStream for chat POST |
| FE-05 | SSE streaming integrated for both chat (token events) and notes (notes_chunk events) | Notes SSE: `EventSource` on GET `/sessions/{id}/start`; Chat SSE: `EventSource` on GET `/chat/stream?session_id=...&message=...` (per PRD) or fetch+ReadableStream if POST is used in Phase 5 implementation |
</phase_requirements>

---

## Summary

Phase 6 builds the complete Next.js 14 UI on top of a scaffold that already exists (routes, components, types, lib — all as `// TODO: implement` stubs). The stack is fully locked from Phase 1 and the PRD: Next.js 14.2.0, TypeScript, Tailwind CSS 3.3, react-dropzone 14.2.3, react-markdown 9.0.1, remark-gfm 4.0.0. No new runtime dependencies are required except `@microsoft/fetch-event-source` — needed only if Phase 5 implements the chat endpoint as POST (which is the correct architectural choice given the message body). The existing `next.config.mjs` already configures a rewrite proxy from `/api/*` to `http://localhost:8000/*`, so all API calls use relative `/api/...` paths from the frontend.

The most technically demanding part of this phase is SSE streaming. The PRD specifies six named SSE event types (`token`, `citations`, `done`, `error`, `notes_chunk`, `notes_done`). For notes (GET `/sessions/{id}/start`), the native `EventSource` API works cleanly. For chat (`POST /chat/stream` with JSON body), the native `EventSource` API cannot send a request body — either Phase 5 must use GET with query params (as shown in the PRD's `lib/sse.ts` example) or the frontend must use `fetch` + `ReadableStream` manual parsing or `@microsoft/fetch-event-source`. This is the single open question for this phase.

The three-panel study session layout is a Tailwind grid. All components already have stubs at the correct file paths per the PRD file tree. The planner must implement each stub in the correct order: shared lib first (`api.ts`, `sse.ts`), then page components that depend on them.

**Primary recommendation:** Implement `lib/api.ts` and `lib/sse.ts` first in plan 06-01 alongside the knowledge page, since every subsequent plan depends on the API client. Use `EventSource` for notes streaming (GET) and clarify chat endpoint method with Phase 5 before finalizing `sse.ts`.

---

## Standard Stack

### Core (Already Installed — No Changes Needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 14.2.0 | App Router framework | Locked in Phase 1; PRD specifies Next.js 14 |
| react | ^18 | Component model | Locked in Phase 1 |
| typescript | ^5 | Type safety | Locked in Phase 1 |
| tailwindcss | ^3.3.0 | Utility CSS | Locked in Phase 1; already configured |
| react-dropzone | ^14.2.3 | Drag-and-drop file upload | PRD requirement; already in package.json |
| react-markdown | ^9.0.1 | Render notes markdown | PRD requirement; already in package.json |
| remark-gfm | ^4.0.0 | GFM tables/strikethrough in markdown | Already in package.json |

### Supporting (May Need to Install)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @microsoft/fetch-event-source | ^2.0.1 | POST-based SSE streaming | Only if Phase 5 implements `/chat/stream` as POST with JSON body (recommended); skipped if GET with query params is used |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| native EventSource | @microsoft/fetch-event-source | fetch-event-source required when SSE endpoint needs POST body (chat); native EventSource works for GET endpoints (notes) |
| Tailwind grid | CSS modules | Tailwind already configured; CSS modules adds build complexity with no benefit |
| useState polling | SWR/React Query | SWR/React Query not in package.json; useState+setInterval is sufficient for the 3s polling window |

**Installation (conditional):**
```bash
# Only install if Phase 5 implements /chat/stream as POST:
npm install @microsoft/fetch-event-source
```

---

## Architecture Patterns

### Existing Project Structure (Do Not Change)

```
frontend/src/
├── app/
│   ├── page.tsx                    # Home → redirect to /knowledge
│   ├── layout.tsx                  # Root layout (add nav here)
│   ├── globals.css                 # Tailwind base
│   ├── knowledge/
│   │   └── page.tsx                # FE-01: upload + source list
│   ├── goals/
│   │   ├── new/page.tsx            # FE-02: goal creation form
│   │   └── [id]/page.tsx           # FE-03: goal detail + progress
│   └── study/
│       └── [sessionId]/page.tsx    # FE-04: three-panel session
├── components/
│   ├── KnowledgeUpload.tsx         # Dropzone + URL field (FE-01)
│   ├── GoalForm.tsx                # Goal creation form (FE-02)
│   ├── StudyPlan.tsx               # Session card list (FE-03)
│   ├── ProgressBar.tsx             # Progress bar (FE-03)
│   ├── SessionNotes.tsx            # react-markdown panel (FE-04)
│   ├── ChatPanel.tsx               # SSE chat UI (FE-04, FE-05)
│   └── QuizPanel.tsx               # MCQ flow (FE-04)
├── lib/
│   ├── api.ts                      # All fetch calls to backend
│   └── sse.ts                      # SSE connection helpers
└── types/index.ts                  # Already complete — all types defined
```

**Key insight:** `types/index.ts` is fully implemented already — all TypeScript types mirror the backend schemas. Never modify or duplicate these types; import from `@/types` everywhere.

### Pattern 1: API Client (`lib/api.ts`)

**What:** Typed fetch wrappers for every backend endpoint. All paths use `/api/...` which the `next.config.mjs` rewrite proxies to `http://localhost:8000/...`.
**When to use:** Every component that needs data from the backend calls these functions, never raw `fetch`.

```typescript
// Source: knowledge from next.config.mjs rewrite + PRD section 9
const API_BASE = '/api'  // next.config.mjs rewrites /api/* → backend:8000/*

// Knowledge endpoints
export async function listSources(): Promise<KnowledgeSource[]> {
  const res = await fetch(`${API_BASE}/knowledge/`)
  if (!res.ok) throw new Error(`Failed: ${res.status}`)
  return res.json()
}

export async function uploadSource(formData: FormData): Promise<{ source_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/knowledge/upload`, { method: 'POST', body: formData })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function getSourceStatus(sourceId: string): Promise<IngestionStatus> {
  const res = await fetch(`${API_BASE}/knowledge/${sourceId}/status`)
  if (!res.ok) throw new Error(`Status failed: ${res.status}`)
  return res.json()
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/knowledge/${sourceId}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 204) throw new Error(`Delete failed: ${res.status}`)
}

// Goals endpoints
export async function createGoal(data: CreateGoalRequest): Promise<StudyPlan> {
  const res = await fetch(`${API_BASE}/goals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Create goal failed: ${res.status}`)
  return res.json()
}

export async function getGoalPlan(goalId: string): Promise<StudyPlan> {
  const res = await fetch(`${API_BASE}/goals/${goalId}`)
  if (!res.ok) throw new Error(`Get plan failed: ${res.status}`)
  return res.json()
}

// Quiz endpoints
export async function generateQuiz(sessionId: string): Promise<QuizQuestion[]> {
  const res = await fetch(`${API_BASE}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`Generate quiz failed: ${res.status}`)
  return res.json()
}

export async function submitQuiz(submission: QuizSubmissionRequest): Promise<QuizResult> {
  const res = await fetch(`${API_BASE}/quiz/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(submission),
  })
  if (!res.ok) throw new Error(`Submit quiz failed: ${res.status}`)
  return res.json()
}
```

### Pattern 2: SSE Streaming (`lib/sse.ts`)

**What:** Helper functions that encapsulate SSE connections for notes and chat. Returns cleanup function for `useEffect`.
**When to use:** Called from `SessionNotes.tsx` (notes stream) and `ChatPanel.tsx` (chat stream).

```typescript
// Source: PRD section 10.2 + SSE event format section 4.2
// Notes streaming — GET endpoint, native EventSource works
export function streamNotes(
  sessionId: string,
  onChunk: (chunk: string) => void,
  onDone: (totalChars: number) => void,
  onError: (msg: string) => void
): () => void {
  const es = new EventSource(`/api/sessions/${sessionId}/start`)

  es.addEventListener('notes_chunk', (e) => {
    const data = JSON.parse(e.data)
    onChunk(data.content)
  })
  es.addEventListener('notes_done', (e) => {
    const data = JSON.parse(e.data)
    es.close()
    onDone(data.total_chars)
  })
  es.addEventListener('error', (e) => {
    es.close()
    onError('Notes stream error')
  })

  return () => es.close()
}

// Chat streaming — if Phase 5 uses GET with query params (per PRD):
export function streamChat(
  sessionId: string,
  message: string,
  onToken: (token: string) => void,
  onCitations: (chunks: RetrievedChunk[]) => void,
  onDone: () => void,
  onError: (msg: string) => void
): () => void {
  const url = `/api/chat/stream?session_id=${sessionId}&message=${encodeURIComponent(message)}`
  const es = new EventSource(url)

  es.addEventListener('token', (e) => onToken(JSON.parse(e.data).content))
  es.addEventListener('citations', (e) => onCitations(JSON.parse(e.data).chunks))
  es.addEventListener('done', () => { es.close(); onDone() })
  es.addEventListener('error', () => { es.close(); onError('Chat stream error') })

  return () => es.close()
}

// Alternative: if Phase 5 uses POST for /chat/stream (architecturally better)
// Install: npm install @microsoft/fetch-event-source
// import { fetchEventSource } from '@microsoft/fetch-event-source'
//
// export function streamChatPost(sessionId, message, onToken, onCitations, onDone, onError) {
//   const ctrl = new AbortController()
//   fetchEventSource('/api/chat/stream', {
//     method: 'POST',
//     headers: { 'Content-Type': 'application/json' },
//     body: JSON.stringify({ session_id: sessionId, message }),
//     signal: ctrl.signal,
//     onmessage(ev) {
//       if (ev.event === 'token') onToken(JSON.parse(ev.data).content)
//       else if (ev.event === 'citations') onCitations(JSON.parse(ev.data).chunks)
//       else if (ev.event === 'done') { ctrl.abort(); onDone() }
//       else if (ev.event === 'error') { ctrl.abort(); onError(JSON.parse(ev.data).message) }
//     },
//     onerror(err) { ctrl.abort(); onError(String(err)) },
//   })
//   return () => ctrl.abort()
// }
```

### Pattern 3: Status Polling

**What:** Poll ingestion status every 3s while a source is not terminal (not `ready` or `failed`).
**When to use:** `KnowledgeUpload.tsx` immediately after upload returns a `source_id`.

```typescript
// Source: PRD section 10.1 "Poll /knowledge/{id}/status every 3s during ingestion"
// In a "use client" component:
useEffect(() => {
  if (!pendingSourceIds.length) return

  const interval = setInterval(async () => {
    const updates = await Promise.all(
      pendingSourceIds.map(id => getSourceStatus(id))
    )
    // Update sources state; remove from pending if status is 'ready' or 'failed'
    setSources(prev => prev.map(s => {
      const update = updates.find(u => u.source_id === s.id)
      return update ? { ...s, status: update.status } : s
    }))
    setPendingSourceIds(prev =>
      prev.filter(id => {
        const s = updates.find(u => u.source_id === id)
        return s && s.status !== 'ready' && s.status !== 'failed'
      })
    )
  }, 3000)

  return () => clearInterval(interval)
}, [pendingSourceIds])
```

### Pattern 4: react-dropzone Upload

**What:** Drag-and-drop zone that calls `/knowledge/upload` with `FormData`.
**When to use:** `KnowledgeUpload.tsx` — the drop handler sends `multipart/form-data`.

```typescript
// Source: react-dropzone docs + PRD section 10.1
// Note: MUST be "use client" — useDropzone is a client hook
'use client'
import { useDropzone } from 'react-dropzone'

const { getRootProps, getInputProps, isDragActive } = useDropzone({
  accept: { 'application/pdf': ['.pdf'] },
  maxSize: 50 * 1024 * 1024,  // 50MB per PRD
  multiple: false,
  onDrop: async (acceptedFiles) => {
    const file = acceptedFiles[0]
    const formData = new FormData()
    formData.append('file', file)
    // Do NOT set Content-Type header — browser sets multipart boundary automatically
    const result = await uploadSource(formData)
    // Add source_id to pending polling list
  }
})
```

### Pattern 5: Three-Panel Study Session Layout

**What:** Three horizontal panels using Tailwind grid with fixed heights and internal scroll.
**When to use:** `/study/[sessionId]/page.tsx`.

```tsx
// Source: Tailwind CSS docs — grid columns + overflow
<div className="grid grid-cols-3 gap-4 h-screen p-4">
  {/* Notes panel */}
  <div className="col-span-1 overflow-y-auto border rounded-lg p-4">
    <SessionNotes sessionId={sessionId} />
  </div>

  {/* Chat panel */}
  <div className="col-span-1 overflow-y-auto border rounded-lg p-4 flex flex-col">
    <ChatPanel sessionId={sessionId} />
  </div>

  {/* Quiz panel */}
  <div className="col-span-1 overflow-y-auto border rounded-lg p-4">
    {showQuiz ? <QuizPanel sessionId={sessionId} /> : (
      <div className="flex items-center justify-center h-full">
        <button onClick={() => setShowQuiz(true)}>Start Quiz</button>
      </div>
    )}
  </div>
</div>
```

### Pattern 6: Dynamic Route Page (Next.js 14)

**What:** In Next.js 14, `params` in page components is a plain object (not a Promise — that changed in Next.js 15).
**When to use:** `/goals/[id]/page.tsx` and `/study/[sessionId]/page.tsx`.

```typescript
// Source: Next.js 14 official docs — params is synchronous in v14
// NOTE: In Next.js 15 params became a Promise — this project uses 14.2.0
export default function GoalDetailPage({ params }: { params: { id: string } }) {
  const goalId = params.id
  // ...
}

export default function StudySessionPage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId
  // ...
}
```

### Anti-Patterns to Avoid

- **Forgetting `'use client'` on components using hooks:** `useDropzone`, `useState`, `useEffect`, `EventSource` all require client components. Every interactive component in this phase needs the directive.
- **Setting Content-Type on FormData uploads:** Let the browser set `multipart/form-data` with the correct boundary automatically; manually setting it breaks the upload.
- **Passing SSE cleanup to component re-renders:** Always return the `es.close()` cleanup from `useEffect` to prevent zombie connections on re-renders or navigation.
- **Using `params` as Promise in Next.js 14:** The Promise-based `params` pattern is Next.js 15+. This project is locked to 14.2.0 — use `params.id` directly.
- **Using absolute `NEXT_PUBLIC_API_URL` for SSE:** Use relative `/api/...` paths so the `next.config.mjs` rewrite proxy handles routing in Docker. Never hardcode `http://localhost:8000` in component code.
- **Server Components for interactive UI:** All pages in this phase need interactivity (polling, SSE, form state). Make pages `'use client'` or keep pages as server components and extract interactive parts into separate client components.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Drag-and-drop file upload | Custom drag event handlers | `useDropzone` from react-dropzone | Handles drag state, file validation, browser quirks, accessibility |
| Markdown rendering | Custom markdown parser | `ReactMarkdown` with `remarkPlugins={[remarkGfm]}` | Handles GFM tables, code blocks, XSS safety |
| SSE with POST body | Manual `fetch` + raw `ReadableStream` SSE parser | `@microsoft/fetch-event-source` | Handles reconnection, named events, abort signals, error recovery |
| Status pill colors | Custom class logic | Tailwind conditional classes with a `statusColor` map | Consistent design, no runtime CSS injection |
| Form validation | Custom validation logic | Native HTML `required` + TypeScript type checking | Sufficient for V1 scope |

**Key insight:** The heavy lifting (streaming, markdown, drag-drop) is already covered by the installed libraries. The implementation work is wiring, not infrastructure building.

---

## Common Pitfalls

### Pitfall 1: SSE Proxy Buffering

**What goes wrong:** The `next.config.mjs` rewrite proxy buffers the SSE response and delivers all chunks at once when the stream closes — defeating streaming.
**Why it happens:** Next.js development server may buffer proxied responses; nginx/reverse proxy default buffering.
**How to avoid:** The backend must set `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers. The frontend uses relative `/api/` paths (not direct `http://localhost:8000`) so the rewrite proxy is in the path. In the Docker dev environment, direct `EventSource` to `http://localhost:8000` (bypassing the Next.js proxy) is an option if buffering occurs, using `NEXT_PUBLIC_API_URL` env var.
**Warning signs:** Notes or chat chunks arrive all at once instead of progressively.

### Pitfall 2: EventSource Cannot Send POST Body

**What goes wrong:** Chat requires a message body — native `EventSource` only supports GET.
**Why it happens:** The `EventSource` Web API specification only supports GET requests.
**How to avoid:** The PRD's `lib/sse.ts` example uses GET with query params (`?session_id=...&message=...`). If Phase 5 implements chat as POST (more correct for large messages), switch to `@microsoft/fetch-event-source`. Coordinate with Phase 5 before implementing `sse.ts`.
**Warning signs:** Long messages get truncated in URL query params; URL length limits hit.

### Pitfall 3: react-dropzone Requires `'use client'`

**What goes wrong:** `useDropzone` crashes in a server component with "cannot use hooks in server component".
**Why it happens:** react-dropzone uses browser APIs and React hooks internally.
**How to avoid:** Every component file that calls `useDropzone` must have `'use client'` as its first line.
**Warning signs:** Build error: "You're importing a component that needs useState. It only works in a Client Component."

### Pitfall 4: Multi-Select Source IDs

**What goes wrong:** Goal form sends `knowledge_source_ids` as comma-separated string instead of `string[]`.
**Why it happens:** HTML `<select multiple>` returns a `FileList`-like object, not a plain array.
**How to avoid:** Use `Array.from(event.target.selectedOptions).map(o => o.value)` or manage selection with `useState<string[]>` and checkbox inputs.
**Warning signs:** Backend rejects goal creation with 422 validation error on `knowledge_source_ids`.

### Pitfall 5: Notes Stream Auto-Trigger

**What goes wrong:** Notes start streaming every time the component mounts, including re-renders.
**Why it happens:** `useEffect` with wrong dependency array re-runs the `EventSource` connection.
**How to avoid:** Use a `hasStarted` ref or state flag to ensure `POST /sessions/{id}/start` is called exactly once per session visit. Clear the flag on session ID change.
**Warning signs:** Duplicate notes chunks appear; network tab shows multiple SSE connections.

### Pitfall 6: Citation Chips Rendering

**What goes wrong:** Citation data from SSE arrives as a separate `citations` event after the `done` event, or arrives before rendering is complete.
**Why it happens:** The `citations` SSE event is asynchronous and separate from `token` events.
**How to avoid:** Accumulate citations in state during streaming; render citation chips below the complete message only after `done` fires. Use a `Map<messageIndex, RetrievedChunk[]>` keyed by message position.
**Warning signs:** Citation chips flash and disappear, or appear before the assistant message text.

---

## Code Examples

Verified patterns from official sources and PRD specification:

### SSE Event Types (from PRD section 4.2)

```
// Notes events:
event: notes_chunk
data: {"type": "notes_chunk", "content": "## Cell Structure\n\nThe cell..."}

event: notes_done
data: {"type": "notes_done", "total_chars": 3420}

// Chat events:
event: token
data: {"type": "token", "content": "Osmosis is"}

event: citations
data: {"type": "citations", "chunks": [{...RetrievedChunk...}]}

event: done
data: {"type": "done", "strategy_used": "pageindex", "latency_ms": 1240}

event: error
data: {"type": "error", "message": "PageIndex tree not found"}
```

### react-markdown with remark-gfm (Notes Panel)

```typescript
// Source: react-markdown docs + PRD section 10
'use client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Use inside SessionNotes.tsx
<ReactMarkdown remarkPlugins={[remarkGfm]}>
  {notesContent}
</ReactMarkdown>
```

### Status Pill Component

```typescript
// Source: derived from PRD requirements + Tailwind CSS
const STATUS_COLORS: Record<IngestionStatus, string> = {
  pending:              'bg-gray-100 text-gray-600',
  indexing_pageindex:   'bg-blue-100 text-blue-600',
  indexing_vectors:     'bg-yellow-100 text-yellow-600',
  ready:                'bg-green-100 text-green-700',
  failed:               'bg-red-100 text-red-600',
}

function StatusPill({ status }: { status: IngestionStatus }) {
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[status]}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
```

### Session Card State Logic

```typescript
// Source: derived from PRD FE-03 and session status enum
// Session availability rules:
// - session 1 is always available if goal is active
// - session N is available only if session N-1 is 'complete'
// - 'complete' sessions show quiz score badge
function getSessionState(session: StudySession, previousSession?: StudySession) {
  if (session.status === 'complete') return 'complete'
  if (session.status === 'in_progress') return 'in_progress'
  if (session.session_number === 1) return 'available'
  if (previousSession?.status === 'complete') return 'available'
  return 'locked'
}
```

### URL Field Upload

```typescript
// Source: PRD section 10.1 — URL field alongside dropzone
async function handleUrlSubmit(url: string) {
  const formData = new FormData()
  formData.append('url', url)
  // No 'file' key — backend accepts either file OR url
  const result = await uploadSource(formData)
  setPendingSourceIds(prev => [...prev, result.source_id])
}
```

### Quiz Flow State Machine

```typescript
// Source: derived from PRD FE-04 and quiz requirements
type QuizPhase = 'idle' | 'generating' | 'active' | 'results'

// State transitions:
// idle → 'Start Quiz' button clicked → generating
// generating → quiz questions loaded → active
// active → all 5 questions answered + submitted → results
// results → 'Complete Session' clicked → navigate back to goal detail
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pages Router | App Router | Next.js 13 (stable 14) | File-based routing in `app/` dir; layouts compose automatically |
| `getServerSideProps` | Server Components + `fetch` | Next.js 13 | Data fetching in async server components |
| `useRouter().query` for params | `params` prop in page | Next.js 13 App Router | Direct `params.id` access in page components |
| EventSource for POST SSE | @microsoft/fetch-event-source | Ongoing | POST SSE with body/headers requires library |
| Webpack | Turbopack (optional) | Next.js 14 | `next dev --turbopack` optional; project uses default webpack |

**Deprecated/outdated in this project's context:**
- `next.config.ts` (PRD shows this but project uses `.mjs`): The actual file is `next.config.mjs` — use the `.mjs` version, ignore PRD's mention of `.ts`.
- `params` as Promise: Only applies to Next.js 15+; this project is 14.2.0 where params is synchronous.

---

## Open Questions

1. **Chat SSE endpoint: GET vs POST**
   - What we know: PRD section 10.2 specifies GET with query params (`/chat/stream?session_id=...&message=...`). Architecturally, POST with JSON body is better for longer messages. Phase 5 is not yet implemented.
   - What's unclear: Which HTTP method will Phase 5 use for `/chat/stream`?
   - Recommendation: Plan `lib/sse.ts` to implement both patterns. Default to the GET pattern (per PRD) in 06-01; if Phase 5 uses POST, update `sse.ts` before implementing `ChatPanel.tsx`.

2. **Session start trigger: explicit vs automatic**
   - What we know: PRD shows `POST /sessions/{id}/start` triggers note generation SSE stream. It's unclear if this is called when the user navigates to the study page or only when they click a "Start Session" button.
   - What's unclear: The PRD says "User can start a session, triggering SSE-streamed note generation" — does this require an explicit button click or auto-starts?
   - Recommendation: Auto-start notes streaming on page load for sessions with status `pending` or `in_progress`. If notes already exist (`notes_markdown` is non-null), display saved notes without streaming.

3. **Notes persistence and re-display**
   - What we know: `StudySession.notes_markdown` stores generated notes. If a user navigates back to a completed session, notes should display from the stored value, not re-stream.
   - What's unclear: Does `GET /goals/{id}` include `notes_markdown` per session?
   - Recommendation: Check `notes_markdown` on load; stream only if null. `GET /goals/{id}` may need to include this field — confirm with Phase 5 implementation.

---

## Sources

### Primary (HIGH confidence)

- PRD `scholar_v1_prd.md` sections 4.2, 9, 10 — SSE event format, API endpoints, frontend page specs
- `frontend/package.json` — exact library versions locked in Phase 1
- `frontend/next.config.mjs` — rewrite proxy configuration
- `frontend/src/types/index.ts` — complete TypeScript types already defined
- Next.js official docs (nextjs.org/docs/app) — App Router patterns, params behavior in v14

### Secondary (MEDIUM confidence)

- `softgrade.org/sse-with-fastapi-react-langgraph` — confirmed `@microsoft/fetch-event-source` required for POST SSE
- `pedroalonso.net/blog/sse-nextjs-real-time-notifications` — EventSource lifecycle pattern verified
- Multiple 2025 sources — SSE headers (`X-Accel-Buffering: no`, `Cache-Control: no-cache`) required for streaming proxy passthrough

### Tertiary (LOW confidence)

- WebSearch results on three-panel Tailwind layout — standard `grid grid-cols-3` pattern is reliable but exact spacing/responsiveness may need tuning during implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are locked from Phase 1; versions confirmed in `package.json`
- Architecture patterns: HIGH — file structure matches PRD exactly; types fully defined; API endpoints specified in PRD section 9
- SSE streaming: MEDIUM-HIGH — EventSource pattern is well-documented; POST/GET question for chat remains open until Phase 5 is implemented
- Pitfalls: HIGH — all identified pitfalls verified against official docs or confirmed by multiple community sources

**Research date:** 2026-03-19
**Valid until:** 2026-04-18 (30 days — stack is stable)

---

## Plan Outline for Planner

The roadmap specifies 4 plans. Recommended task breakdown:

| Plan | Scope | Key Components |
|------|-------|----------------|
| 06-01 | Knowledge base page (FE-01) | `lib/api.ts` full implementation, `lib/sse.ts` skeleton, `KnowledgeUpload.tsx`, `knowledge/page.tsx`, status polling |
| 06-02 | Goal creation + goal detail (FE-02, FE-03) | `GoalForm.tsx`, `StudyPlan.tsx`, `ProgressBar.tsx`, `goals/new/page.tsx`, `goals/[id]/page.tsx` |
| 06-03 | Study session page + notes + chat SSE (FE-04, FE-05) | `SessionNotes.tsx`, `ChatPanel.tsx`, `sse.ts` complete, `study/[sessionId]/page.tsx` three-panel layout |
| 06-04 | Quiz panel + Complete Session flow (FE-04) | `QuizPanel.tsx`, quiz state machine, MCQ render, results display, session completion |
