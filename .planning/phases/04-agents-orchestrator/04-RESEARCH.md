# Phase 4: Agents & Orchestrator - Research

**Researched:** 2026-03-19
**Domain:** LangGraph state machines, LangChain agents, SSE streaming, LangSmith tracing, SQLite persistence
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GOAL-01 | User can create a study goal with title, topic, deadline (days), level, sessions/week, and knowledge source selection | SQLite schema already exists (study_goals table); Pydantic schemas defined in schemas.py |
| GOAL-02 | Planner agent generates a sequenced multi-session plan (session_count = ceil(deadline_days / 7 * sessions_per_week)) | ChatOpenAI.with_structured_output(StudyPlanOutput) pattern; gpt-4o-mini confirmed working |
| GOAL-03 | Each session has title, topic, estimated_minutes, and sequential session_number | StudySession schema exists; SessionPlan Pydantic model detailed in PRD |
| GOAL-04 | User can retrieve a goal's full study plan including session statuses | aiosqlite query pattern matches existing codebase; StudyPlan schema defined |
| SESS-01 | User can start a session, triggering SSE-streamed note generation grounded in retrieved context | sse-starlette EventSourceResponse + ChatOpenAI.astream() pattern; retrieve() orchestrator available |
| SESS-02 | Notes stream via SSE notes_chunk events — never blocks waiting for full generation | StreamingResponse with async generator; notes_chunk event format specified in PRD |
| SESS-03 | Every factual claim in notes cites source book title and page number | Context injection via retrieved RetrievedChunk objects; citation format in PRD prompt spec |
| SESS-04 | Notes are persisted in SQLite after generation completes | aiosqlite UPDATE study_sessions after stream completes; existing get_db() helper |
| CHAT-01 | User can send a chat message and receive an SSE-streamed response grounded in retrieved context | ChatOpenAI.astream() + EventSourceResponse; token/citations/done event sequence |
| CHAT-02 | Chat agent answers ONLY from provided context — refuses to answer from training data | System prompt enforcement; "Answer ONLY from context" instruction in PRD |
| CHAT-03 | Each chat response includes citation chunks referencing source book and page | citations SSE event after streaming completes; RetrievedChunk list serialized as JSON |
| CHAT-04 | Full chat history persisted in LangGraph state (SqliteSaver) — survives browser refresh | AsyncSqliteSaver.from_conn_string() in FastAPI lifespan; thread_id = goal_id pattern |
| OBS-01 | Every agent call traced in LangSmith with cost and latency | LANGCHAIN_TRACING_V2=true env var; automatic tracing via LangChain callbacks |
</phase_requirements>

---

## Summary

Phase 4 builds four agent modules (Planner, Note Generator, Session Chat, Quiz Agent) plus the LangGraph orchestrator that ties them together. The foundation is already in place: SQLite schema exists (study_goals, study_sessions, chat_history tables), Pydantic schemas are complete (StudyGoal, StudySession, ChatMessage, QuizQuestion, ScholarState), the retrieval layer (retrieve()) is fully operational, and all agent files are stubs awaiting implementation.

The critical technical decisions are already locked in state: gpt-4o-mini as LLM, LangGraph SqliteSaver for chat persistence, SSE over WebSockets for streaming, LangSmith tracing via environment variables. The primary complexity in this phase is threading the async streaming pipeline correctly — ChatOpenAI.astream() → async generator → sse-starlette EventSourceResponse — without blocking or leaking connections.

The `langgraph-checkpoint-sqlite` package must be added to requirements.txt as a separate dependency (split from langgraph core in v0.2). AsyncSqliteSaver should be initialized in FastAPI's lifespan context manager and stored as app state. The planner and quiz agents use synchronous structured output (asyncio.to_thread bridge), while note generator and chat use async streaming directly.

**Primary recommendation:** Implement agents in dependency order: Planner (sync, structured output) → Note Generator (async streaming SSE) → Session Chat (async streaming SSE + AsyncSqliteSaver checkpointing) → Quiz Agent (sync structured output + scoring). Wire LangSmith via env vars — no code changes needed beyond LANGCHAIN_TRACING_V2=true.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 0.2.76 (pinned) | State machine orchestrator with checkpointing | Non-negotiable per project decisions; SqliteSaver for chat history survival |
| langgraph-checkpoint-sqlite | latest compatible | SqliteSaver / AsyncSqliteSaver | Split from langgraph core in v0.2; required separate install |
| langchain-openai | 0.2.14 (pinned) | ChatOpenAI with streaming and structured output | Already installed; with_structured_output + astream already used in router.py |
| langsmith | 0.1.147 (pinned) | LangSmith tracing — automatic via env vars | Already in requirements; zero-code tracing via LANGCHAIN_TRACING_V2=true |
| sse-starlette | latest | EventSourceResponse for FastAPI 0.115 | FastAPI native SSE only in 0.135+; project is on 0.115.0 |
| aiosqlite | 0.20.0 (pinned) | Async SQLite access | Already installed; used in router.py and hybrid_retriever.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Bridges sync LangChain calls into async | asyncio.to_thread() for planner and quiz structured output (sync → async boundary) |
| pydantic | 2.x (transitive) | StudyPlanOutput, QuizQuestion structured output schemas | with_structured_output() requires Pydantic BaseModel |
| json | stdlib | Serialize SSE event payloads | All SSE events send JSON via data field |
| math | stdlib | ceil(deadline_days / 7 * sessions_per_week) | Session count formula from PRD spec |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | Native FastAPI SSE (fastapi.sse) | Native SSE only available in FastAPI 0.135+; project is pinned to 0.115.0 — cannot use |
| AsyncSqliteSaver (lifespan) | SqliteSaver (sync, per-request) | Sync saver requires check_same_thread=False and doesn't scale; async saver is required for FastAPI async context |
| gpt-4o-mini | gpt-4o | Cost — 4o-mini is ~10x cheaper; locked decision, no alternatives |
| LangSmith env var tracing | Manual callback injection | Env var is zero-code; already configured in docker-compose; no reason to change |

**Installation — add to requirements.txt:**
```bash
pip install langgraph-checkpoint-sqlite sse-starlette
```

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/agents/
├── planner.py          # Planner agent: structured output → StudyPlan
├── note_generator.py   # Note generator: retrieve + stream SSE notes_chunk events
├── session_chat.py     # Chat agent: retrieve + stream SSE token/citations/done events
├── quiz_agent.py       # Quiz generation + synchronous scoring (evaluate_quiz)
├── prompts.py          # All system/user prompts centralized
└── orchestrator.py     # LangGraph StateGraph + AsyncSqliteSaver checkpointer
```

### Pattern 1: Planner Agent (Sync Structured Output via asyncio.to_thread)

**What:** gpt-4o-mini with Pydantic structured output generates the sequenced session plan. The LangChain structured output chain is synchronous; bridge to async with asyncio.to_thread.

**When to use:** Any agent call that uses with_structured_output and doesn't need streaming.

```python
# Source: router.py (existing codebase pattern — identical approach)
import asyncio
from math import ceil
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from app.config import settings

class SessionPlan(BaseModel):
    session_number: int
    title: str
    topic: str
    estimated_minutes: int
    focus_chapters: list[str]

class StudyPlanOutput(BaseModel):
    sessions: list[SessionPlan]
    rationale: str

_llm = ChatOpenAI(model=settings.llm_model, temperature=0)
_planner_chain = _llm.with_structured_output(StudyPlanOutput)

async def generate_plan(goal_title: str, topic: str, level: str,
                        deadline_days: int, sessions_per_week: int,
                        source_titles: list[str]) -> StudyPlanOutput:
    session_count = ceil(deadline_days / 7 * sessions_per_week)
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Goal: {goal_title}\nTopic: {topic}\nLevel: {level}\nSessions: {session_count}\nSources: {source_titles}"},
    ]
    return await asyncio.to_thread(_planner_chain.invoke, messages)
```

### Pattern 2: Note Generator (Async SSE Streaming)

**What:** retrieve() fetches context chunks, then ChatOpenAI.astream() generates notes token by token, yielding notes_chunk SSE events.

**When to use:** Any agent that must stream output to the frontend via SSE.

```python
# Source: PRD section 8.2 + LangChain astream docs
from langchain_openai import ChatOpenAI
from app.retrieval.hybrid_retriever import retrieve

async def stream_notes(session_id: str, topic: str, source_ids: list[str], level: str):
    """Async generator yielding SSE-formatted JSON strings."""
    retrieval = await retrieve(topic, source_ids, top_k=8)
    context = _format_context(retrieval.chunks)

    llm = ChatOpenAI(model=settings.llm_model, temperature=0, streaming=True)
    messages = [
        {"role": "system", "content": NOTE_SYSTEM_PROMPT.format(level=level)},
        {"role": "user", "content": f"Topic: {topic}\n\nContext:\n{context}"},
    ]

    full_notes = []
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_notes.append(token)
            yield f"event: notes_chunk\ndata: {json.dumps({'type': 'notes_chunk', 'content': token})}\n\n"

    notes_markdown = "".join(full_notes)
    # Persist to SQLite after stream completes
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("UPDATE study_sessions SET notes_markdown=? WHERE id=?",
                         (notes_markdown, session_id))
        await db.commit()
    yield f"event: notes_done\ndata: {json.dumps({'type': 'notes_done', 'total_chars': len(notes_markdown)})}\n\n"
```

```python
# FastAPI endpoint using sse-starlette (NOT native fastapi.sse — wrong version)
from sse_starlette import EventSourceResponse

@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str):
    # fetch goal context...
    return EventSourceResponse(
        stream_notes(session_id, topic, source_ids, level),
        media_type="text/event-stream"
    )
```

### Pattern 3: Session Chat Agent (Streaming + AsyncSqliteSaver)

**What:** On each user message — re-retrieve context, stream response tokens, send citations event, persist to LangGraph checkpoint.

```python
# Source: PRD section 8.3 + LangGraph SqliteSaver docs
async def stream_chat(session_id: str, goal_id: str, message: str,
                      source_ids: list[str], app_state):
    """Async generator for SSE chat events."""
    retrieval = await retrieve(message, source_ids, top_k=5)
    context = _format_context(retrieval.chunks)

    # Build messages with full chat history from LangGraph state
    config = {"configurable": {"thread_id": goal_id}}
    # ... get history from checkpointer ...

    llm = ChatOpenAI(model=settings.llm_model, temperature=0, streaming=True)
    system_msg = CHAT_SYSTEM_PROMPT.format(context=context)

    full_response = []
    async for chunk in llm.astream([system_msg, *history, {"role": "user", "content": message}]):
        token = chunk.content
        if token:
            full_response.append(token)
            yield f"event: token\ndata: {json.dumps({'type': 'token', 'content': token})}\n\n"

    # Send citations event
    yield f"event: citations\ndata: {json.dumps({'type': 'citations', 'chunks': [c.model_dump() for c in retrieval.chunks]})}\n\n"
    yield f"event: done\ndata: {json.dumps({'type': 'done', 'strategy_used': retrieval.strategy_used, 'latency_ms': retrieval.latency_ms})}\n\n"
```

### Pattern 4: AsyncSqliteSaver in FastAPI Lifespan

**What:** AsyncSqliteSaver must be initialized as a context manager at startup and stored as app state. Individual endpoints receive it as a dependency.

```python
# Source: LangGraph docs + FastAPI lifespan pattern
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_pgvector_schema()
    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_path) as checkpointer:
        app.state.checkpointer = checkpointer
        yield
    # checkpointer connection closed automatically on shutdown
```

### Pattern 5: Quiz Agent (Structured Output + Sync Scoring)

**What:** Generation uses structured output (asyncio.to_thread); scoring is pure Python with no LLM call.

```python
# Source: PRD section 8.4
class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]   # exactly 4
    correct_index: int
    explanation: str

class QuizOutput(BaseModel):
    questions: list[QuizQuestion]

async def generate_quiz(session_id: str, notes_markdown: str,
                        topic: str, level: str) -> list[QuizQuestion]:
    _quiz_chain = ChatOpenAI(model=settings.llm_model, temperature=0.3).with_structured_output(QuizOutput)
    messages = [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT.format(level=level)},
        {"role": "user", "content": f"Topic: {topic}\n\nNotes:\n{notes_markdown}"},
    ]
    result = await asyncio.to_thread(_quiz_chain.invoke, messages)
    return result.questions

def evaluate_quiz(questions: list[QuizQuestion], answers: dict[str, int]) -> QuizResult:
    """Pure Python — no LLM call needed."""
    correct_count = sum(
        1 for q in questions
        if answers.get(q.id) == q.correct_index
    )
    return QuizResult(
        score=correct_count / len(questions),
        total_questions=len(questions),
        correct_count=correct_count,
        per_question=[{
            "question_id": q.id,
            "correct": answers.get(q.id) == q.correct_index,
            "explanation": q.explanation,
        } for q in questions],
    )
```

### Pattern 6: LangSmith Tracing (Zero Code Required)

**What:** LangSmith traces every LangChain/LangGraph call automatically when env vars are set. No callback injection needed.

```python
# docker-compose.yml already has:
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}
# LANGCHAIN_PROJECT=scholar-v1

# config.py already has:
# langchain_tracing_v2: bool = False  (set True in .env)
# langchain_project: str = "scholar"

# No code changes needed — LangSmith auto-traces all ChatOpenAI and LangGraph calls
# when LANGCHAIN_TRACING_V2=true is set in environment.
```

### Anti-Patterns to Avoid

- **Streaming=False on ChatOpenAI when using .astream():** Always pass `streaming=True` to ChatOpenAI when using `.astream()`. Without it, the model buffers the full response before returning.
- **Using SqliteSaver (sync) in async FastAPI context:** Use AsyncSqliteSaver instead. SqliteSaver.async methods raise NotImplementedError.
- **Initializing AsyncSqliteSaver per-request:** Must be created once in lifespan and stored as `app.state.checkpointer`. Creating per-request opens/closes SQLite connections and causes lock contention.
- **Using fastapi.sse.EventSourceResponse:** Only available in FastAPI 0.135+. The project uses 0.115.0. Use `from sse_starlette import EventSourceResponse` instead.
- **Persisting quiz correct_index to frontend during active quiz:** QuizQuestion.correct_index must be stripped from the API response during question delivery; only returned in QuizResult after submission.
- **Blocking the event loop with LangChain structured output:** with_structured_output().invoke() is synchronous. Always bridge with asyncio.to_thread() — see existing router.py for the exact pattern already used.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chat history persistence across refreshes | Custom SQLite read/write per message | AsyncSqliteSaver (LangGraph) | LangGraph manages checkpoint versioning, thread isolation, and state merging — complex to replicate |
| SSE event formatting | Manual "data: ...\n\n" string building in every endpoint | sse-starlette EventSourceResponse | Handles keep-alive, content-type header, proper flush, and connection lifecycle |
| Structured JSON output from LLM | Parse LLM text with regex or json.loads | ChatOpenAI.with_structured_output(PydanticModel) | Handles retry on invalid JSON, validates schema, handles model refusals gracefully |
| LLM call tracing / cost tracking | Custom logging wrapper around ChatOpenAI | LangSmith (env var activation) | Provides per-node cost, latency, token counts, run trees — impossible to replicate cleanly |
| Session count math | Complex date calculation | `ceil(deadline_days / 7 * sessions_per_week)` | PRD mandates this exact formula — one line |

**Key insight:** Every "custom solution" in this domain has been solved by the LangChain/LangGraph ecosystem. The project already imported these libraries — use them fully.

---

## Common Pitfalls

### Pitfall 1: Missing langgraph-checkpoint-sqlite Package
**What goes wrong:** `ImportError: cannot import name 'SqliteSaver' from 'langgraph.checkpoint.sqlite'`
**Why it happens:** In LangGraph v0.2, SqliteSaver was moved to a separate `langgraph-checkpoint-sqlite` package. The main `langgraph` package no longer bundles it.
**How to avoid:** Add `langgraph-checkpoint-sqlite` to requirements.txt before any other work.
**Warning signs:** Import error at startup or first checkpoint operation.

### Pitfall 2: AsyncSqliteSaver Not Started Before Graph Compilation
**What goes wrong:** RuntimeError or None checkpointer when graph tries to save state.
**Why it happens:** AsyncSqliteSaver requires `async with` initialization before use. If compiled before the context manager starts, the connection is None.
**How to avoid:** Initialize in FastAPI lifespan with `async with AsyncSqliteSaver.from_conn_string(path) as cp:` and compile graph inside the block. Store compiled graph as `app.state.graph`.
**Warning signs:** Graph runs but state is not persisted; browser refresh loses chat history.

### Pitfall 3: SSE Generator Not Flushed
**What goes wrong:** Frontend receives all chunks at once when the LLM finishes, defeating the purpose of streaming.
**Why it happens:** Nginx/proxy buffering or missing `X-Accel-Buffering: no` header. Also triggered by not using `EventSourceResponse` (using plain `StreamingResponse` without correct headers).
**How to avoid:** Use sse-starlette's EventSourceResponse which sets correct headers automatically. In docker-compose dev, buffering is less of an issue but set headers anyway.
**Warning signs:** Frontend shows content only after a long pause, not incrementally.

### Pitfall 4: LangSmith Tracing Not Appearing
**What goes wrong:** Agent calls execute but no traces appear in LangSmith dashboard.
**Why it happens:** `LANGCHAIN_TRACING_V2` must be the string `"true"` (not boolean) in environment, AND `LANGCHAIN_API_KEY` (not `LANGSMITH_API_KEY`) must be set. The project config names it `langsmith_api_key` but LangChain reads `LANGCHAIN_API_KEY`.
**How to avoid:** Verify both env vars in docker-compose. Test with a simple `ChatOpenAI.invoke()` and check LangSmith UI before building all agents.
**Warning signs:** No runs appear in LangSmith project; no error is raised (tracing failure is silent by default).

### Pitfall 5: quiz correct_index Leaked to Frontend
**What goes wrong:** Student can inspect network response and see all correct answers before submitting.
**Why it happens:** Returning `QuizQuestion` objects directly from the generate endpoint without stripping `correct_index`.
**How to avoid:** Create a separate `QuizQuestionPublic` schema (no `correct_index` field) for the generate endpoint. Store full questions (with `correct_index`) only in SQLite, keyed by session_id.
**Warning signs:** Quiz questions in API response contain `correct_index` field.

### Pitfall 6: SSE Connection Left Open on Client Error
**What goes wrong:** Server-side generator keeps running (and LLM streaming tokens) after client disconnects.
**Why it happens:** The async generator has no disconnect detection. LLM streaming continues billable API calls.
**How to avoid:** sse-starlette handles client disconnect detection automatically. Wrap generator in try/except `asyncio.CancelledError`.
**Warning signs:** LLM API costs spike; generator never terminates in logs.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Existing Pattern: asyncio.to_thread for Sync LangChain (from router.py)
```python
# Source: backend/app/retrieval/router.py (existing working code)
decision = await asyncio.to_thread(
    _router_chain.invoke,
    [{"role": "user", "content": f"Classify this query: {query}"}],
)
```
**Reuse exactly this pattern** for planner and quiz structured output calls.

### SSE Endpoint with sse-starlette
```python
# Source: sse-starlette docs (verified working with FastAPI 0.115)
from sse_starlette import EventSourceResponse

@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, request: Request):
    async def event_generator():
        async for event in stream_notes(session_id, ...):
            if await request.is_disconnected():
                break
            yield event
    return EventSourceResponse(event_generator())
```

### AsyncSqliteSaver in Lifespan
```python
# Source: LangGraph checkpoint-sqlite docs + FastAPI lifespan docs
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_pgvector_schema()
    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_path) as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield
```

### LangSmith Tracing — Environment Variables Only
```python
# Source: LangSmith docs (auto-tracing, no code needed)
# .env file:
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=scholar-v1

# Every ChatOpenAI call and LangGraph node is automatically traced
# Includes: cost per call, latency per node, token counts, full prompts
```

### SQLite Persistence Pattern (from existing codebase)
```python
# Source: backend/app/retrieval/router.py (existing aiosqlite pattern)
async with aiosqlite.connect(settings.sqlite_path) as db:
    await db.execute(
        "UPDATE study_sessions SET notes_markdown=?, status=? WHERE id=?",
        (notes_markdown, "in_progress", session_id)
    )
    await db.commit()
```

### Session Count Formula
```python
# Source: PRD section 8.1 (GOAL-02 specification)
from math import ceil
session_count = ceil(deadline_days / 7 * sessions_per_week)
# Example: deadline_days=14, sessions_per_week=3 → ceil(14/7*3) = ceil(6.0) = 6
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SqliteSaver bundled in langgraph | Separate `langgraph-checkpoint-sqlite` package | LangGraph v0.2 | Must add to requirements.txt explicitly |
| Manual SSE formatting with StreamingResponse | sse-starlette EventSourceResponse | 2023–2024 | Handles headers, keep-alive, disconnect automatically |
| FastAPI 0.135+ native SSE (fastapi.sse) | Not available in FastAPI 0.115 | FastAPI 0.135 release | Project must use sse-starlette; cannot use native |
| LangGraph 0.2.x | LangGraph 1.1.3 current | March 2026 | Project is pinned to 0.2.76 — do NOT upgrade; breaking API changes between 0.2 and 1.x |

**Deprecated/outdated:**
- `from langgraph.checkpoint.sqlite import SqliteSaver` with langgraph<0.2: worked when bundled; now requires separate package install.
- `ChatOpenAI(streaming=True)` as a standalone argument: still works but streaming=True is only needed when using `.stream()` or `.astream()` — can be omitted from constructor and specified at call time in newer versions.

---

## Open Questions

1. **LangGraph orchestrator scope in Phase 4**
   - What we know: The PRD shows a full LangGraph StateGraph (plan → generate_notes → session_active → quiz → evaluate_quiz → session_complete → loop/END). The roadmap Plan 04-01 says "Planner agent and LangGraph orchestrator with SqliteSaver."
   - What's unclear: Whether the LangGraph StateGraph needs to be fully implemented in Phase 4 or whether a simpler function-based orchestrator suffices for Phase 4, with the graph only used for checkpointing chat history.
   - Recommendation: Build the minimal LangGraph graph needed for chat history checkpointing (CHAT-04) in Phase 4. The full session state machine (plan → notes → quiz loop) can be simplified to direct function calls since the frontend drives session transitions. The graph's primary value in Phase 4 is the SqliteSaver checkpointer for chat continuity.

2. **LANGCHAIN_API_KEY vs LANGSMITH_API_KEY naming**
   - What we know: LangChain reads `LANGCHAIN_API_KEY` from environment for LangSmith. The project config has `langsmith_api_key` as the Pydantic field name.
   - What's unclear: Whether pydantic-settings maps `langsmith_api_key` to `LANGCHAIN_API_KEY` or `LANGSMITH_API_KEY`.
   - Recommendation: Set both `LANGCHAIN_API_KEY` and `LANGSMITH_API_KEY` in .env.example for safety. Verify tracing works with a single test call before building all agents.

3. **chat_history table vs LangGraph checkpointer**
   - What we know: The SQLite schema has a `chat_history` table AND LangGraph AsyncSqliteSaver creates its own checkpoint tables. These are separate.
   - What's unclear: Whether CHAT-04 (history survives refresh) requires only AsyncSqliteSaver (sufficient) or also requires the `chat_history` table for the API GET endpoint.
   - Recommendation: Use AsyncSqliteSaver as the source of truth for chat history in CHAT-04. The `chat_history` table can be used for the API to list historical messages without requiring LangGraph state deserialization.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/retrieval/router.py` — asyncio.to_thread bridge pattern, confirmed working in Phase 3
- `backend/app/models/schemas.py` — all Pydantic schemas already defined (StudyGoal, StudySession, ChatMessage, QuizQuestion, ScholarState)
- `backend/app/db/database.py` — SQLite schema with study_goals, study_sessions, chat_history tables
- `backend/app/config.py` — LangSmith config (langchain_tracing_v2, langchain_project, langsmith_api_key)
- `https://pypi.org/project/langgraph-checkpoint-sqlite/` — version 3.0.3, import paths confirmed
- `scholar_v1_prd.md` — definitive spec for all agent prompts, SSE event formats, session count formula

### Secondary (MEDIUM confidence)
- `https://blog.langchain.com/langgraph-v0-2/` — confirmed SqliteSaver moved to separate package in v0.2
- `https://pypi.org/project/sse-starlette/` — version 3.3.3, EventSourceResponse import path
- `https://fastapi.tiangolo.com/tutorial/server-sent-events/` — native SSE requires FastAPI 0.135+; confirms project must use sse-starlette
- WebSearch: LangGraph AsyncSqliteSaver + FastAPI lifespan pattern — multiple consistent sources

### Tertiary (LOW confidence)
- LangGraph 1.1.3 latest version (March 2026) — confirms major version jump from 0.2.76 pinned; avoid upgrading without testing
- LANGCHAIN_API_KEY vs LANGSMITH_API_KEY naming — requires runtime verification

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing requirements.txt + PRD + PyPI confirms all packages; only addition is langgraph-checkpoint-sqlite and sse-starlette
- Architecture: HIGH — all patterns are direct extensions of existing Phase 3 code (router.py asyncio.to_thread pattern, aiosqlite pattern, hybrid_retriever.py pattern)
- Pitfalls: HIGH — SqliteSaver package split is documented; SSE library version issue is confirmed; LangSmith env var naming is a known source of confusion
- SSE approach: MEDIUM-HIGH — sse-starlette confirmed compatible with Starlette/FastAPI; native FastAPI SSE version incompatibility confirmed

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (30 days — LangGraph/LangSmith APIs are stable; SSE pattern is stable)
