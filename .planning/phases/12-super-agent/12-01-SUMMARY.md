---
phase: 12-super-agent
plan: "01"
subsystem: super-agent
tags: [super-agent, sse, langgraph, cross-source-retrieval]
dependency_graph:
  requires: []
  provides: [stream_super_chat, POST /super/chat/stream]
  affects: [backend/app/main.py]
tech_stack:
  added: []
  patterns: [SSE-POST, LangGraph-checkpointer, all-ready-sources-query]
key_files:
  created:
    - backend/app/agents/super_agent.py
    - backend/app/routers/super.py
  modified:
    - backend/app/main.py
decisions:
  - "top_k=8 for super agent retrieval to handle larger cross-source pool per research recommendation"
  - "Checkpoint channel_values excludes goal_id — super chat is not goal-scoped unlike session_chat"
  - "Broader try/except Exception added (beyond CancelledError) to yield SSE error event before re-raising, preventing silent broken streams"
metrics:
  duration: "2 min"
  completed: "2026-03-22"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 12 Plan 01: Super Agent Summary

**One-liner:** Cross-knowledge-base persistent SSE chat via `stream_super_chat()` querying all ready sources with LangGraph thread persistence using caller-provided UUID.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create super_agent.py — cross-source stream_super_chat generator | a5de631 | backend/app/agents/super_agent.py |
| 2 | Create routers/super.py and register in main.py | 990114e | backend/app/routers/super.py, backend/app/main.py |

## What Was Built

**super_agent.py** — `stream_super_chat(message, thread_id, checkpointer)` async generator:
- Queries `knowledge_sources WHERE status='ready'` to retrieve ALL ready source IDs (not scoped to any goal or session)
- Guards empty source pool: yields `event: error` with `{"type": "error", "content": "No books indexed yet"}` and returns immediately
- Retrieves context with `top_k=8` (larger than session_chat's top_k=5 to serve broader source pool)
- Loads/saves LangGraph checkpoint using caller-provided `thread_id` unchanged — server never generates it
- Checkpoint `channel_values` stores `{"messages": updated_messages}` only — no `goal_id` field
- SSE event format (token/citations/done) is identical to `/sessions/{id}/chat`
- Dual exception handling: `CancelledError` returns silently; broader `Exception` yields SSE error event before re-raising

**routers/super.py** — `POST /super/chat/stream` endpoint:
- `SuperChatRequest(message: str, thread_id: str = Field(min_length=1))` — empty thread_id rejected at validation
- No DB session/goal lookup — passes directly to `stream_super_chat()`
- Respects client disconnect via `request.is_disconnected()` check in event generator

**main.py** — super router registered alongside existing routers; `/super/chat/stream` confirmed in app routes.

## Verification Results

All checks passed:
- `from app.agents.super_agent import stream_super_chat` — OK
- `from app.routers.super import router` — OK
- `/super/chat/stream` present in `app.routes` — confirmed
- `SuperChatRequest(message='hi', thread_id='')` raises Pydantic validation error — OK

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- backend/app/agents/super_agent.py — FOUND
- backend/app/routers/super.py — FOUND

Commits:
- a5de631 — FOUND
- 990114e — FOUND
