---
phase: 12-super-agent
plan: "02"
subsystem: super-agent
tags: [super-agent, tdd, pytest, sse, mocking]
dependency_graph:
  requires: [12-01]
  provides: [backend/tests/test_super_agent.py]
  affects: []
tech_stack:
  added: []
  patterns: [TDD-mocked-asyncio, async-context-manager-mock, pytest-asyncio]
key_files:
  created:
    - backend/tests/test_super_agent.py
  modified: []
decisions:
  - "Tests went GREEN immediately (implementation pre-existed from Plan 01) — same pattern as Phase 10 Plan 03"
  - "aiosqlite mock requires nested async context managers (connect CM → db.execute CM → cursor.fetchall)"
  - "LLM mock uses async generator function (fake_astream) rather than AsyncMock to properly support async for"
metrics:
  duration: "2 min"
  completed: "2026-03-22"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 12 Plan 02: Super Agent TDD Suite Summary

**One-liner:** 10-test pytest suite verifying SUP-01 through SUP-04 super agent behaviors using fully mocked aiosqlite, retrieve, LLM, and checkpointer — all GREEN without live infrastructure.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Write and pass all 10 super agent tests (SUP-01 through SUP-04 + router) | e3e7d93 | backend/tests/test_super_agent.py |

## What Was Built

**backend/tests/test_super_agent.py** — 10 pytest tests (>80 lines, 366 total):

- **SUP-01** (`test_sup01_retrieve_called_with_all_source_ids`): mocks aiosqlite returning 2 rows; asserts `retrieve()` called with `source_ids=["source_id_a", "source_id_b"]`
- **SUP-02a** (`test_sup02_empty_kb_yields_error_event`): mocks empty aiosqlite result; asserts exactly 1 SSE event starting with `event: error\n` with `content: "No books indexed yet"`
- **SUP-02b** (`test_sup02_retrieve_not_called_when_empty_kb`): same empty-KB setup; asserts `retrieve()` was NOT called
- **SUP-03** (`test_sup03_thread_id_passed_unchanged_to_checkpointer`): asserts `checkpointer.aput` called with `{"configurable": {"thread_id": "my-frontend-uuid"}}` unchanged
- **SUP-04a** (`test_sup04_sse_event_sequence`): asserts token events precede citations, citations precede done
- **SUP-04b** (`test_sup04_token_event_json_shape`): asserts token event payload has `type` and `content` keys
- **SUP-04c** (`test_sup04_citations_event_json_shape`): asserts citations event payload has `type` and `chunks` keys
- **SUP-04d** (`test_sup04_done_event_json_shape`): asserts done event payload has `type`, `strategy_used`, `latency_ms` keys
- **ROUTER-200** (`test_router_returns_200_on_valid_payload`): FastAPI TestClient POST with valid payload → HTTP 200
- **ROUTER-422** (`test_router_returns_422_on_empty_thread_id`): FastAPI TestClient POST with `thread_id=""` → HTTP 422

**Mock infrastructure helpers:**
- `_make_aiosqlite_mock(rows)` — builds nested async context manager chain simulating `aiosqlite.connect` → `db.execute` → `cursor.fetchall`
- `_make_retrieve_mock(chunks, strategy_used, latency_ms)` — AsyncMock returning result with `.chunks`, `.strategy_used`, `.latency_ms`
- `_make_llm_mock(tokens)` — sync function returning a MagicMock whose `.astream()` is a real async generator (not AsyncMock), required for `async for` compatibility
- `_make_checkpointer_mock()` — AsyncMock with `.aget_tuple` → None and `.aput` as AsyncMock
- `collect(gen)` — async helper to drain async generator into list

## Verification Results

```
10 passed, 3 warnings in 0.69s
Exit: 0
```

All 10 tests GREEN. No tests skipped or xfailed. Warnings are upstream deprecation notices (Python 3.14 Pydantic V1 compatibility) — not caused by this code.

## Deviations from Plan

**Tests went GREEN immediately (no RED phase possible)**

Same pattern as Phase 10 Plan 03: implementation pre-existed from Plan 01, so tests were GREEN on first run. The TDD plan specified RED→GREEN→REFACTOR, but since `stream_super_chat` and the router were already correct, the RED phase was skipped. Tests still fully verify all stated behaviors.

**LLM async generator — sync function instead of AsyncMock**

The plan specified `AsyncMock` for `get_llm().astream()`. However, `async for chunk in llm.astream(messages)` requires a true async generator, not an AsyncMock coroutine. Used a regular function returning a MagicMock whose `.astream` attribute is an actual `async def` generator function. This correctly satisfies the `async for` protocol.

## Self-Check: PASSED

Files created:
- backend/tests/test_super_agent.py — FOUND

Commits:
- e3e7d93 — FOUND
