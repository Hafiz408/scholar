# Phase 5: API Layer - Research

**Researched:** 2026-03-19
**Domain:** FastAPI REST endpoints, SSE streaming, aiosqlite async patterns, LangGraph agent wiring
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QUIZ-01 | User can generate a 5-question MCQ quiz for a session, grounded in session notes and retrieved context | Quiz generate endpoint wires to quiz_agent.generate_quiz(); stores questions in SQLite; returns list[QuizQuestion] with correct_index stripped |
| QUIZ-02 | Each question has 4 options with one unambiguously correct answer and a plausible distractor set | Enforced by quiz agent prompt + QuizQuestion schema (already defined in schemas.py); API passes through agent output |
| QUIZ-03 | User can submit quiz answers and receive a score (0.0–1.0) with per-question explanation | Quiz submit endpoint calls evaluate_quiz(); returns QuizResult with score, correct_count, per_question list |
| QUIZ-04 | Quiz score is stored in study_sessions.quiz_score; session is marked complete after submission | aiosqlite UPDATE study_sessions SET quiz_score=?, status='complete' WHERE id=?; endpoint triggers goal progress re-check |
</phase_requirements>

---

## Summary

Phase 5 is a pure API wiring phase — all agents exist (built in Phase 4) and all data models exist (defined in schemas.py). The task is to implement the four remaining router files (`goals.py`, `sessions.py`, `chat.py`, `quiz.py`), register them in `main.py`, and add CORS middleware for the Next.js frontend. The phase's narrow scope (4 QUIZ requirements) means the planner should treat goal/session/chat endpoints as infrastructure unlocking frontend, while quiz endpoints are the primary deliverables.

The critical technical challenge is SSE streaming from FastAPI to the client. FastAPI 0.115+ ships a built-in `EventSourceResponse` from `fastapi.sse` with `ServerSentEvent` objects — this is the standard approach as of 2025-26. For notes and chat streams, the pattern is an async generator that pulls tokens from the LangGraph `astream()` call and yields `ServerSentEvent` objects with named event types (`token`, `notes_chunk`, `citations`, `done`). The PRD defines the exact SSE event format that must be matched.

The second challenge is LangGraph + aiosqlite concurrency. The `SqliteSaver` checkpointer uses a SQLite file; the same file is used by `aiosqlite` for business data. SQLite allows only one writer at a time, so the pattern must serialize writes. The known safe approach: use `SqliteSaver` (sync) for LangGraph checkpoints and `aiosqlite` (async) for business data queries, keeping them as separate connection contexts. Never mix the two in the same transaction.

**Primary recommendation:** Use FastAPI's built-in `EventSourceResponse` + `ServerSentEvent` from `fastapi.sse` for all SSE endpoints. Wire agents by importing from `app.agents.*`. Use `aiosqlite` dependency injection (`Depends(get_db)`) for all business data reads/writes matching the existing `knowledge.py` pattern.

---

## Standard Stack

### Core (all already in requirements.txt — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.0 | Web framework; `EventSourceResponse` + `ServerSentEvent` from `fastapi.sse` | Already installed; 0.115+ includes built-in SSE support |
| aiosqlite | 0.20.0 | Async SQLite for business data (goals, sessions, quiz, chat) | Already installed; matches `knowledge.py` pattern |
| langgraph | 0.2.76 | Agent orchestration; `SqliteSaver` checkpointer; `astream()` for streaming | Already installed; Phase 4 output |
| langchain-openai | 0.2.14 | LLM calls inside agents | Already installed |
| pydantic | v2 (via fastapi) | Request/response validation | Already in schemas.py |

### No new packages required

Phase 5 requires zero additional pip packages. All necessary libraries were installed in Phase 1/2.

**Installation:** None — `requirements.txt` is complete.

---

## Architecture Patterns

### Recommended Router Structure

```
backend/app/routers/
├── knowledge.py    # [DONE] — reference implementation
├── goals.py        # POST /goals, GET /goals/{id}
├── sessions.py     # POST /sessions/{id}/start  (SSE)
├── chat.py         # POST /chat/stream           (SSE)
└── quiz.py         # POST /quiz/generate, POST /quiz/submit
```

### Pattern 1: Standard JSON Router (goals.py, quiz.py)

**What:** POST/GET endpoints that call agents and read/write SQLite, return JSON.
**When to use:** Non-streaming operations — goal creation, quiz generate, quiz submit.

```python
# Source: existing knowledge.py pattern + FastAPI official docs
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from app.db.database import get_db
from app.models.schemas import StudyGoal, StudyPlan, QuizQuestion, QuizSubmission, QuizResult

router = APIRouter()

@router.post("/goals", response_model=StudyPlan, status_code=201)
async def create_goal(goal_in: GoalCreate, db: aiosqlite.Connection = Depends(get_db)):
    # 1. Validate knowledge_source_ids exist
    # 2. Call planner agent: plan = await planner.generate_plan(goal_in)
    # 3. INSERT INTO study_goals ...
    # 4. INSERT INTO study_sessions for each session in plan
    # 5. Return StudyPlan(goal=..., sessions=..., total_sessions=N, completed_sessions=0)
    ...
```

### Pattern 2: SSE Streaming Router (sessions.py, chat.py)

**What:** POST endpoints that return `EventSourceResponse` with an async generator.
**When to use:** Notes generation (`/sessions/{id}/start`) and chat (`/chat/stream`).

```python
# Source: FastAPI official SSE docs (fastapi.tiangolo.com/tutorial/server-sent-events/)
import json
from collections.abc import AsyncIterable
from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()

@router.post("/sessions/{session_id}/start", response_class=EventSourceResponse)
async def start_session(session_id: str) -> AsyncIterable[ServerSentEvent]:
    # 1. Load session from SQLite, validate status == 'pending'
    # 2. UPDATE status → 'in_progress'
    # 3. Retrieve context via hybrid_retriever
    async for chunk in note_generator.stream_notes(session_id, context):
        yield ServerSentEvent(
            data=json.dumps({"type": "notes_chunk", "content": chunk}),
            event="notes_chunk"
        )
    # 4. Persist final notes to SQLite
    yield ServerSentEvent(
        data=json.dumps({"type": "notes_done", "total_chars": total}),
        event="notes_done"
    )
```

```python
# Chat SSE pattern
@router.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(body: ChatRequest) -> AsyncIterable[ServerSentEvent]:
    # 1. Load session, retrieve context
    async for event in session_chat.astream(body.message, body.session_id):
        if event["type"] == "token":
            yield ServerSentEvent(
                data=json.dumps({"type": "token", "content": event["content"]}),
                event="token"
            )
    yield ServerSentEvent(
        data=json.dumps({"type": "citations", "chunks": [c.dict() for c in citations]}),
        event="citations"
    )
    yield ServerSentEvent(data=json.dumps({"type": "done"}), event="done")
```

### Pattern 3: Quiz Submit with SQLite Update

**What:** POST `/quiz/submit` evaluates answers, stores score, marks session complete.
**When to use:** Quiz submission (QUIZ-03, QUIZ-04).

```python
@router.post("/quiz/submit", response_model=QuizResult)
async def submit_quiz(submission: QuizSubmission, db: aiosqlite.Connection = Depends(get_db)):
    # 1. Load stored quiz questions from SQLite (questions stored after generate)
    # 2. Call evaluate_quiz(questions, submission.answers)
    # 3. UPDATE study_sessions SET quiz_score=result.score, status='complete'
    #    WHERE id=submission.session_id
    # 4. Check if all sessions complete → UPDATE study_goals SET status='complete'
    # 5. Return QuizResult
    ...
```

### Pattern 4: CORS Middleware in main.py

**What:** Add CORSMiddleware before registering routers.
**When to use:** Always — required for Next.js frontend on localhost:3000.

```python
# Source: FastAPI official CORS docs (fastapi.tiangolo.com/tutorial/cors/)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Pattern 5: Router Registration in main.py

```python
# Add after existing knowledge_router registration
from app.routers.goals import router as goals_router
from app.routers.sessions import router as sessions_router
from app.routers.chat import router as chat_router
from app.routers.quiz import router as quiz_router

app.include_router(goals_router, prefix="/goals", tags=["goals"])
app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(quiz_router, prefix="/quiz", tags=["quiz"])
```

### Pattern 6: Stripping correct_index before returning quiz questions

**What:** QuizQuestion has `correct_index` — must NOT be sent during quiz generation (only revealed after submission).
**How:** Return a filtered response model, or use `response_model_exclude` on the endpoint.

```python
class QuizQuestionPublic(BaseModel):
    """QuizQuestion without correct_index — safe to send to frontend."""
    id: str
    question: str
    options: list[str]
    explanation: str  # shown after submission; excluded from generate response too

@router.post("/quiz/generate", response_model=list[QuizQuestionPublic])
async def generate_quiz(session_id: str):
    questions = await quiz_agent.generate_quiz(session_id)
    # Store full questions (with correct_index) in SQLite for later evaluation
    await _store_quiz_questions(questions, session_id)
    # Return stripped version
    return [QuizQuestionPublic(...) for q in questions]
```

### Recommended SQLite Schema for Quiz Storage

The `db/database.py` SQLITE_SCHEMA does not have a quiz_questions table. Phase 5 must add one:

```sql
CREATE TABLE IF NOT EXISTS quiz_questions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,         -- JSON array of 4 strings
    correct_index INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY (session_id) REFERENCES study_sessions(id)
);
```

This table is needed so `/quiz/submit` can look up the correct answers without calling the LLM again.

### Anti-Patterns to Avoid

- **Passing `correct_index` in the generate response:** The frontend must not see correct answers during quiz — always use a separate response model without this field.
- **Calling the quiz agent again during submit:** Store questions after generation; retrieve from SQLite on submit. Calling the LLM twice is expensive and non-deterministic.
- **Blocking SSE with synchronous agent calls:** All agent calls inside SSE generators must be async-native or wrapped with `asyncio.to_thread`. See Phase 3 decision: `asyncio.to_thread` bridges sync LangChain into async handlers.
- **Global mutable LangGraph state:** Each goal gets its own `thread_id` (= goal_id) in the LangGraph config. Never share state across goals.
- **SSE with GET for POST operations:** Use POST for `/sessions/{id}/start` and `/chat/stream` because they carry a body. The `EventSourceResponse` works fine on POST — this is documented in FastAPI SSE docs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE event formatting | Custom text/event-stream string formatter | `fastapi.sse.ServerSentEvent` + `EventSourceResponse` | Built-in handles keep-alive, headers, W3C compliance |
| Quiz evaluation scoring | Custom scoring loop | `evaluate_quiz()` function built in Phase 4 quiz_agent | Already specified and implemented in Phase 4 |
| Chat history persistence | Manual SQLite insert on every message | LangGraph `SqliteSaver` checkpointer with `thread_id=session_id` | LangGraph state handles serialization, replay, resumability |
| Session status transitions | Ad-hoc status string updates | `UPDATE study_sessions SET status=? WHERE id=?` via `aiosqlite` | SQLite is the single source of truth; no extra state machine needed |
| CORS handling | Manual `OPTIONS` preflight handlers | `CORSMiddleware` from `fastapi.middleware.cors` | Handles all preflight cases, headers, methods automatically |

**Key insight:** Phase 5 is glue code. Every hard problem (agent logic, retrieval, state) is solved in Phase 4 or earlier. The API layer's job is to expose that work through clean HTTP contracts.

---

## Common Pitfalls

### Pitfall 1: SSE Endpoint Returning 422 on POST with Body

**What goes wrong:** Using `EventSourceResponse` as `response_class` on a POST endpoint that takes a JSON body — FastAPI may fail validation or return a 422 if the request body isn't declared as a Pydantic model parameter.
**Why it happens:** EventSourceResponse changes the response model but not the request parsing.
**How to avoid:** Declare the request body as a Pydantic BaseModel parameter (`body: ChatRequest`), not as individual `Query` params, for POST SSE endpoints.
**Warning signs:** 422 Unprocessable Entity on curl tests of `/chat/stream` or `/sessions/{id}/start`.

### Pitfall 2: correct_index Leaking to Frontend

**What goes wrong:** Returning `list[QuizQuestion]` directly from `/quiz/generate` sends `correct_index` in the response.
**Why it happens:** The QuizQuestion schema includes it for internal use (submit evaluation).
**How to avoid:** Define `QuizQuestionPublic` (without `correct_index`) as the `response_model` on the generate endpoint. Store full questions in SQLite immediately after generation.
**Warning signs:** Frontend receives a field called `correct_index` in the quiz generate response body.

### Pitfall 3: LangGraph SqliteSaver Blocking the Event Loop

**What goes wrong:** `SqliteSaver` (sync) used inside an `async def` endpoint freezes the ASGI event loop.
**Why it happens:** Sync I/O blocks the thread that's running the async event loop.
**How to avoid:** Use `asyncio.to_thread()` to wrap any sync LangGraph call (`graph.stream()`, `graph.invoke()`). For async streaming, prefer `astream()` which is natively async. As of LangGraph 0.2.x, `AsyncSqliteSaver` is available — if Phase 4 uses it, the SSE generator can `async for` directly.
**Warning signs:** `/sessions/{id}/start` hangs with no output or response until full notes are generated.

### Pitfall 4: SSE Stream Not Flushing Through Proxy/Docker

**What goes wrong:** SSE events arrive at the client in batches rather than as they're generated.
**Why it happens:** Nginx/Docker's buffering holds chunks until a buffer fills.
**How to avoid:** FastAPI's built-in `EventSourceResponse` automatically sets `X-Accel-Buffering: no` and `Cache-Control: no-cache`. Verify these headers are present in responses. In docker-compose, no extra config needed.
**Warning signs:** Notes appear all at once when the generation completes rather than token-by-token.

### Pitfall 5: quiz_questions Table Not Created on Startup

**What goes wrong:** `/quiz/generate` succeeds but `/quiz/submit` returns 500 — no table to look up stored questions.
**Why it happens:** SQLITE_SCHEMA in `db/database.py` doesn't include `quiz_questions`.
**How to avoid:** Add the `quiz_questions` CREATE TABLE to `SQLITE_SCHEMA` in `db/database.py` and call `init_db()` on lifespan (already called in `main.py`).
**Warning signs:** `OperationalError: no such table: quiz_questions` on first submit call.

### Pitfall 6: knowledge_source_ids JSON Serialization in SQLite

**What goes wrong:** `study_goals.knowledge_source_ids` is a `list[str]` in Python but SQLite stores only TEXT. Reading it back gives a string, not a list.
**Why it happens:** SQLite has no native array type; the existing schema stores it as `TEXT`.
**How to avoid:** `json.dumps(ids)` on write, `json.loads(row["knowledge_source_ids"])` on read. This matches the pattern implied by the existing schema definition in `db/database.py`.
**Warning signs:** Goal retrieval returns `knowledge_source_ids` as a plain string `'["id1","id2"]'` instead of a list.

### Pitfall 7: Goal Progress Not Updating After Session Complete

**What goes wrong:** `/goals/{id}` always shows 0 completed sessions even after quiz submission.
**Why it happens:** No trigger updates `study_goals.status` — must be computed from sessions on read OR explicitly updated on last session complete.
**How to avoid:** On quiz submit, query `COUNT(*) WHERE goal_id=? AND status='complete'` and compare to `total_sessions`. If equal, `UPDATE study_goals SET status='complete'`. The `/goals/{id}` GET computes `completed_sessions` dynamically from the sessions query.
**Warning signs:** Goal progress bar stuck at 0% on frontend goal detail page.

---

## Code Examples

Verified patterns from official sources and project codebase:

### SSE Endpoint with Named Events (POST, returns streaming response)

```python
# Source: https://fastapi.tiangolo.com/tutorial/server-sent-events/
import json
from collections.abc import AsyncIterable
from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()

@router.post("/sessions/{session_id}/start", response_class=EventSourceResponse)
async def start_session(session_id: str) -> AsyncIterable[ServerSentEvent]:
    async for chunk_text in note_generator.stream_notes(session_id):
        yield ServerSentEvent(
            data=json.dumps({"type": "notes_chunk", "content": chunk_text}),
            event="notes_chunk",
        )
    yield ServerSentEvent(
        data=json.dumps({"type": "notes_done"}),
        event="notes_done",
    )
```

### aiosqlite Dependency Injection (matches knowledge.py pattern)

```python
# Source: app/db/database.py get_db() already defined
from fastapi import Depends
import aiosqlite
from app.db.database import get_db

@router.post("/quiz/submit", response_model=QuizResult)
async def submit_quiz(
    submission: QuizSubmission,
    db: aiosqlite.Connection = Depends(get_db)
):
    async with db.execute(
        "SELECT * FROM quiz_questions WHERE session_id = ?",
        (submission.session_id,)
    ) as cursor:
        rows = await cursor.fetchall()
    questions = [_row_to_question(r) for r in rows]
    result = evaluate_quiz(questions, submission.answers)

    await db.execute(
        "UPDATE study_sessions SET quiz_score=?, status='complete' WHERE id=?",
        (result.score, submission.session_id)
    )
    await db.commit()
    return result
```

### CORS + Router Registration in main.py

```python
# Source: FastAPI official docs - fastapi.tiangolo.com/tutorial/cors/
from fastapi.middleware.cors import CORSMiddleware
from app.routers.goals import router as goals_router
from app.routers.sessions import router as sessions_router
from app.routers.chat import router as chat_router
from app.routers.quiz import router as quiz_router

# Add CORS before include_router calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(goals_router, prefix="/goals", tags=["goals"])
app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(quiz_router, prefix="/quiz", tags=["quiz"])
```

### Stripping correct_index for Frontend Safety

```python
# Source: Project schemas.py (QuizQuestion already defined) + PRD Section 9
from pydantic import BaseModel

class QuizQuestionPublic(BaseModel):
    """Safe quiz question for frontend — no correct_index."""
    id: str
    question: str
    options: list[str]

@router.post("/quiz/generate", response_model=list[QuizQuestionPublic])
async def generate_quiz(session_id: str, db: aiosqlite.Connection = Depends(get_db)):
    questions: list[QuizQuestion] = await quiz_agent.generate_quiz(session_id)
    # Store full questions with correct_index in SQLite
    for q in questions:
        await db.execute(
            "INSERT INTO quiz_questions (id, session_id, question, options, correct_index, explanation, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (q.id, session_id, q.question, json.dumps(q.options), q.correct_index, q.explanation, now)
        )
    await db.commit()
    return [QuizQuestionPublic(id=q.id, question=q.question, options=q.options) for q in questions]
```

### LangGraph astream for SSE token streaming

```python
# Source: LangGraph 0.2.x + DEV Community guide (dev.to/kasi_viswanath/...)
async def stream_agent_tokens(session_id: str, message: str) -> AsyncIterable[ServerSentEvent]:
    config = {"configurable": {"thread_id": session_id}}
    async for event in graph.astream(
        {"messages": [HumanMessage(content=message)]},
        config=config,
        stream_mode="messages",
    ):
        # event is (message_chunk, metadata) in stream_mode="messages"
        chunk, metadata = event
        if hasattr(chunk, "content") and chunk.content:
            yield ServerSentEvent(
                data=json.dumps({"type": "token", "content": chunk.content}),
                event="token",
            )
```

---

## API Endpoints Summary (PRD Section 9)

The full API surface Phase 5 must implement:

| Method | Path | Router File | Phase Req |
|--------|------|-------------|-----------|
| POST | `/goals` | goals.py | — (infrastructure for FE) |
| GET | `/goals/{id}` | goals.py | — (infrastructure for FE) |
| POST | `/sessions/{id}/start` | sessions.py | SESS-01, SESS-02 (Phase 4 req, Phase 5 wires) |
| POST | `/chat/stream` | chat.py | CHAT-01 (Phase 4 req, Phase 5 wires) |
| POST | `/quiz/generate` | quiz.py | QUIZ-01, QUIZ-02 |
| POST | `/quiz/submit` | quiz.py | QUIZ-03, QUIZ-04 |

Note: The roadmap assigns QUIZ-01 through QUIZ-04 to Phase 5. SESS-01/SESS-02 and CHAT-01 are Phase 4 agent requirements, but the API endpoints for them are also implemented in Phase 5 (the routers are currently TODO stubs).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `sse-starlette` (third-party) | `fastapi.sse.EventSourceResponse` + `ServerSentEvent` (built-in) | FastAPI 0.115.0 (2024) | No extra dependency; native SSE support |
| `graph.invoke()` (blocking) | `graph.astream()` with `stream_mode="messages"` | LangGraph 0.2+ | Token-level streaming without callbacks |
| Manual SSE string formatting `f"data: {x}\n\n"` | `ServerSentEvent(data=..., event=...)` | FastAPI 0.115+ | Handles keep-alive, headers, W3C spec automatically |

**Deprecated/outdated:**
- `SqliteSaver.from_conn_string()`: Still valid in LangGraph 0.2.76 but check if Phase 4 used `AsyncSqliteSaver` instead — match whatever Phase 4 chose.

---

## Open Questions

1. **AsyncSqliteSaver vs SqliteSaver in Phase 4**
   - What we know: LangGraph 0.2.76 ships both; there are documented issues with `AsyncSqliteSaver.astream_events()` hanging in some configurations (GitHub issue #789)
   - What's unclear: Which checkpointer Phase 4 actually implements (Phase 4 is not yet built)
   - Recommendation: Phase 5 planner should note that if Phase 4 uses `SqliteSaver` (sync), SSE generators must use `asyncio.to_thread()` for graph calls. If Phase 4 uses `AsyncSqliteSaver`, generators can `async for` directly. Either is correct — match Phase 4's choice.

2. **QuizQuestion storage format for options (JSON vs delimited)**
   - What we know: SQLite has no array type; `options: list[str]` must be serialized
   - What's unclear: Whether Phase 4 quiz agent stores anything or leaves all storage to Phase 5
   - Recommendation: Store `options` as `json.dumps(list)` in SQLite and `json.loads()` on read. This is consistent with how `knowledge_source_ids` is handled in study_goals.

3. **Session start idempotency**
   - What we know: `POST /sessions/{id}/start` triggers note generation — if called twice, should it re-generate?
   - What's unclear: PRD doesn't address this case
   - Recommendation: Check current status; if `status == 'in_progress'` or `status == 'complete'`, return a non-streaming 409 Conflict. Only generate notes when `status == 'pending'`.

---

## Sources

### Primary (HIGH confidence)
- `fastapi.tiangolo.com/tutorial/server-sent-events/` — Official FastAPI SSE docs; EventSourceResponse, ServerSentEvent usage, POST SSE support
- `fastapi.tiangolo.com/tutorial/cors/` — Official CORSMiddleware setup
- `/Users/mohammedhafiz/Desktop/Personal/scholar/backend/app/models/schemas.py` — Project schemas: QuizQuestion, QuizSubmission, QuizResult, StudyGoal, StudySession, StudyPlan — all defined
- `/Users/mohammedhafiz/Desktop/Personal/scholar/backend/app/db/database.py` — SQLITE_SCHEMA confirms quiz_questions table is absent; init_db() called on lifespan
- `/Users/mohammedhafiz/Desktop/Personal/scholar/backend/app/routers/knowledge.py` — Reference implementation: aiosqlite pattern, Depends(get_db), HTTPException usage
- `/Users/mohammedhafiz/Desktop/Personal/scholar/scholar_v1_prd.md` — PRD Section 9 (API table), Section 4.2 (SSE event format), Section 8.4 (quiz agent spec)

### Secondary (MEDIUM confidence)
- `dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn` — LangGraph astream() + FastAPI SSE integration pattern (2025-26 guide); stream_mode="messages" for token streaming
- `github.com/langchain-ai/langgraph/issues/789` — Documents AsyncSqliteSaver + astream_events hang issue in LangGraph 0.2.x
- Multiple sources confirm: FastAPI 0.115+ built-in SSE is preferred over sse-starlette for new projects

### Tertiary (LOW confidence)
- Community claim that `AsyncSqliteSaver` is not recommended for production; not verified against official LangGraph 0.2.76 release notes — flag for validation when Phase 4 makes its checkpointer choice.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; all libraries already in requirements.txt and verified against project files
- Architecture: HIGH — PRD Section 9 specifies exact endpoints; SSE format in PRD Section 4.2; schemas fully defined; knowledge.py is a confirmed reference implementation
- Pitfalls: MEDIUM — SSE streaming pitfalls verified via official docs; quiz correct_index leak is a logical deduction from schema; LangGraph blocking pitfall is from GitHub issues (MEDIUM)

**Research date:** 2026-03-19
**Valid until:** 2026-04-18 (FastAPI and LangGraph are relatively stable; SSE API unlikely to change)
