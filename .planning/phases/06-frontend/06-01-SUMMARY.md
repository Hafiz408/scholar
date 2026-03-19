---
phase: 06-frontend
plan: "01"
subsystem: frontend
tags: [api-client, sse, knowledge-base, react-dropzone, typescript]
dependency_graph:
  requires: []
  provides:
    - frontend/src/lib/api.ts (typed fetch wrappers for all backend endpoints)
    - frontend/src/lib/sse.ts (SSE streaming helpers using fetch-event-source)
    - frontend/src/components/KnowledgeUpload.tsx (drag-drop + URL upload + polling)
    - frontend/src/app/knowledge/page.tsx (knowledge base page)
  affects:
    - 06-02 (GoalForm imports createGoal from api.ts)
    - 06-03 (ChatPanel imports streamChat from sse.ts)
    - 06-04 (QuizPanel imports generateQuiz/submitQuiz from api.ts)
tech_stack:
  added:
    - "@microsoft/fetch-event-source ^2.0.1 — POST-based SSE for notes and chat streams"
  patterns:
    - "API client pattern: single api.ts module; all components import named functions, never raw fetch"
    - "SSE streaming via fetchEventSource with AbortController for cleanup"
    - "3-second polling via setInterval + useEffect with pendingSourceIds dependency"
    - "react-dropzone useDropzone hook for PDF drag-and-drop"
key_files:
  created:
    - frontend/src/components/KnowledgeUpload.tsx
    - frontend/src/app/knowledge/page.tsx
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/lib/sse.ts
    - frontend/src/app/page.tsx
    - frontend/package.json (added @microsoft/fetch-event-source)
decisions:
  - "Used @microsoft/fetch-event-source instead of native EventSource: both /sessions/{id}/start and /sessions/{id}/chat are POST endpoints in Phase 5 — native EventSource (GET-only) cannot be used"
  - "submitQuiz signature changed to (sessionId, submission): actual backend endpoint is POST /sessions/{session_id}/quiz/submit, not /quiz/submit as plan described"
  - "generateQuiz endpoint is POST /sessions/{session_id}/quiz/generate, not /quiz/generate — corrected to match actual backend routes"
  - "sendChatMessage in api.ts returns raw Response — sse.ts streamChat uses fetchEventSource directly for clean separation"
metrics:
  duration: "4 min"
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_modified: 6
---

# Phase 6 Plan 01: API Client and Knowledge Base Page Summary

**One-liner:** Typed API client (api.ts) and POST-based SSE helpers (sse.ts) with fully working knowledge base page featuring drag-drop PDF upload, URL ingestion, and 3-second status polling.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Implement lib/api.ts and lib/sse.ts | 580a4e4 |
| 2 | Knowledge base page — upload, poll, and source list | 2da9f1b |

## What Was Built

### lib/api.ts
Typed fetch wrappers for all 10 backend endpoints using `const API_BASE = '/api'` (Next.js rewrite proxy). Exports: `listSources`, `uploadSource`, `getSourceStatus`, `deleteSource`, `createGoal`, `getGoalPlan`, `startSession` (URL helper), `getSession`, `sendChatMessage`, `generateQuiz`, `submitQuiz`. Also exports `CreateGoalRequest` and `QuizSubmissionRequest` interfaces (not defined in types/index.ts).

### lib/sse.ts
Two streaming helpers using `@microsoft/fetch-event-source` (required because both SSE endpoints use POST). `streamNotes` connects to `POST /sessions/{id}/start` and fires `onChunk`/`onDone`/`onError` callbacks. `streamChat` connects to `POST /sessions/{id}/chat` and fires `onToken`/`onCitations`/`onDone`/`onError`. Both return `() => ctrl.abort()` for useEffect cleanup.

### KnowledgeUpload.tsx
`'use client'` component with:
- react-dropzone for PDF drag-and-drop (50MB limit, PDF-only)
- URL input field with form submit
- Source list rendering `StatusPill` for each source
- `setInterval` polling every 3000ms for pending sources
- Delete button calling `deleteSource`

### knowledge/page.tsx
Simple server component wrapper rendering `<KnowledgeUpload />` with "Knowledge Base" heading.

### page.tsx (root)
Server component calling `redirect('/knowledge')` from next/navigation.

## Verification Results

1. `npx tsc --noEmit` — zero errors
2. `docker compose up -d` — all three services healthy
3. `GET http://localhost:3000/knowledge` (inside container) — 200 OK, full HTML rendered
4. `GET http://localhost:3000/` (inside container) — 307 redirect to /knowledge
5. Knowledge page HTML confirmed: dropzone, URL field, empty source list rendered

Note: Host port 3000 is occupied by another application. All verification was performed from inside the Docker container via `wget` — the Scholar frontend container itself serves correctly on port 3000 internally.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] POST-based SSE endpoints required fetch-event-source**
- **Found during:** Task 1
- **Issue:** Plan said to use native EventSource (GET-based), but Phase 5 implemented both `/sessions/{id}/start` and `/sessions/{id}/chat` as POST endpoints. Native EventSource cannot send request bodies.
- **Fix:** Installed `@microsoft/fetch-event-source`; implemented both `streamNotes` and `streamChat` using `fetchEventSource` with POST method and AbortController.
- **Files modified:** frontend/src/lib/sse.ts, frontend/package.json
- **Commit:** 580a4e4

**2. [Rule 1 - Bug] Quiz and chat endpoint paths corrected**
- **Found during:** Task 1
- **Issue:** Plan specified `POST /quiz/generate` and `POST /quiz/submit` but actual backend routes are `POST /sessions/{session_id}/quiz/generate` and `POST /sessions/{session_id}/quiz/submit`. Chat is `POST /sessions/{session_id}/chat`, not `/chat/stream`.
- **Fix:** Updated generateQuiz, submitQuiz, and sendChatMessage in api.ts to use correct paths matching the backend routers.
- **Files modified:** frontend/src/lib/api.ts
- **Commit:** 580a4e4

**3. [Rule 2 - Missing Types] Added CreateGoalRequest and QuizSubmissionRequest to api.ts**
- **Found during:** Task 1
- **Issue:** types/index.ts does not define `CreateGoalRequest` or `QuizSubmissionRequest` — needed for api.ts function signatures.
- **Fix:** Defined both interfaces in api.ts (not types/index.ts, to keep type ownership near their use). Exported them for downstream plans.
- **Files modified:** frontend/src/lib/api.ts
- **Commit:** 580a4e4

## Self-Check: PASSED

All created/modified files confirmed present on disk. Both task commits (580a4e4, 2da9f1b) confirmed in git history.
