# Flows

Every important Scholar flow as a diagram. For component context, see [architecture.md](architecture.md).

---

## 1 — Document Ingestion

Upload returns a `source_id` immediately; processing runs as a background task through four stages. PageIndex tree-building is the expensive step and degrades gracefully on failure.

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI /knowledge
    participant P as Pipeline
    participant PI as PageIndex Builder
    participant EM as Embedder
    participant PG as Postgres/pgvector
    participant FS as Disk

    U->>API: POST /knowledge/upload (PDF or URL)
    API->>PG: INSERT knowledge_sources (status=pending)
    API-->>U: { source_id }  ← returns immediately
    API->>P: BackgroundTask: run_ingestion()

    Note over P: Stage 1 — Text extraction (+ optional vision for diagrams)
    P->>PG: UPDATE page_count

    Note over P: Stage 2 — PageIndex tree (PDF only)
    P->>PG: status = indexing_pageindex
    P->>PI: build_pageindex_tree()
    Note over PI: ~140–220 LLM calls build a hierarchical<br/>tree with node_id + summary + text
    PI->>FS: write {source_id}_tree.json
    PI-->>P: source_id (or None on failure → vector-only)

    Note over P: Stage 3 — Vector embeddings
    P->>PG: status = indexing_vectors
    P->>EM: chunk (600/100) → embed → upsert
    EM->>PG: UPSERT (source_id, chunk_index, content, vector)

    Note over P: Stage 4 — Ready
    P->>PG: status = ready, pageindex_doc_id = source_id (or NULL)

    U->>API: GET /knowledge/{id}/status (poll)
    API-->>U: { status: "ready" }
```

---

## 2 — Retrieval Routing (the grounded-answer path)

Every note and chat message runs through the router, which picks a strategy and dispatches to the retrievers.

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant RO as Router
    participant PI as PageIndex Retriever
    participant VE as Vector Retriever
    participant HY as Hybrid Merger
    participant FS as tree.json
    participant PG as pgvector
    participant LLM as LLM

    API->>RO: classify_query(query, source_ids)
    alt source has no PageIndex tree
        RO-->>API: "vector" (no LLM call)
    else has tree
        RO->>LLM: classify → pageindex | vector | hybrid
        RO-->>API: strategy
    end

    alt pageindex
        API->>PI: fetch_pageindex_chunks()
        PI->>FS: load tree → flatten to skeleton (node_id + title + summary)
        PI->>LLM: "Which node_ids answer: {query}?"
        LLM-->>PI: ["2.1", "3", "1.4"]
        PI->>FS: extract full text of those nodes
        PI-->>API: chunks
    else vector
        API->>VE: vector_search(top_k=5)
        VE->>LLM: embed query
        VE->>PG: cosine similarity WHERE source_id IN (...)
        VE-->>API: chunks
    else hybrid
        par concurrent
            API->>PI: fetch_pageindex_chunks()
        and
            API->>VE: vector_search()
        end
        PI-->>HY: pageindex chunks
        VE-->>HY: vector chunks
        HY->>HY: merge 0.6·PI + 0.4·vec, dedupe by content hash
        HY-->>API: ranked chunks
    end

    API->>LLM: system prompt + context + history + question
    LLM-->>API: streamed, cited answer (SSE)
```

---

## 3 — Study Session Lifecycle

```mermaid
stateDiagram-v2
    [*] --> GoalCreated: POST /goals
    GoalCreated --> PlanGenerated: Planner agent
    note right of PlanGenerated
        N sessions sized to the deadline,
        each with title · topic · estimated_minutes
    end note
    PlanGenerated --> SessionPending: sessions inserted (pending)

    SessionPending --> NotesStreaming: POST /sessions/{id}/start
    note right of NotesStreaming
        retrieve() → Note Generator → SSE markdown
        notes persisted, status → in_progress
    end note
    NotesStreaming --> SessionActive

    SessionActive --> ChatActive: user asks questions
    ChatActive --> SessionActive: grounded SSE answer

    SessionActive --> QuizGenerated: quiz/generate (MCQs from notes)
    QuizGenerated --> QuizSubmitted: quiz/submit (pure-Python scoring)
    QuizSubmitted --> SessionComplete: score saved, status → complete
    QuizSubmitted --> AdaptiveInserted: score < 65%
    AdaptiveInserted --> SessionComplete
    SessionComplete --> [*]
```

---

## 4 — Adaptive Follow-up (score < 65%)

When a quiz is failed, the adaptive planner inserts a remedial session **after** the current one and renumbers the rest — atomically, so a second failure can't corrupt the order.

```mermaid
sequenceDiagram
    participant U as User
    participant API as /sessions/{id}/quiz/submit
    participant EV as evaluate_quiz()
    participant AD as Adaptive Planner
    participant DB as Postgres

    U->>API: submit answers
    API->>EV: score (pure Python)
    EV-->>API: score = 0.4
    API->>DB: UPDATE session: quiz_score, status=complete
    alt score below 0.65
        API->>AD: handle_quiz_failure(session_id)
        AD->>DB: fetch session_number fresh by UUID
        AD->>AD: generate a targeted remedial session
        AD->>DB: shift later session_numbers +1, INSERT follow-up
        AD-->>API: { followup_session }
    end
    API-->>U: { score, followup_session_added, followup_session }
    Note over U: Frontend shows an "Adaptive session added" banner
```

---

## 5 — Final Cumulative Test

Available once every session is complete. Questions are drawn across sessions; passing marks the whole goal complete.

```mermaid
stateDiagram-v2
    [*] --> Idle: all sessions complete → TestPanel appears
    Idle --> Generating: POST /goals/{id}/test/generate
    note right of Generating
        Final-Test agent pulls 1–2 MCQs per session
        (capped at 15), each tagged with its session
    end note
    Generating --> Active: questions rendered
    Active --> Scored: POST /goals/{id}/test/submit
    note right of Scored
        ≥ 70% → goal marked complete (confetti 🎉)
        weak sessions (below 50%) surfaced for review
    end note
    Scored --> [*]
```

---

## 6 — Super Agent (cross-knowledge-base chat)

A single chat grounded across **all** ready sources, with history keyed by a client-owned `thread_id` (from `localStorage`) so it persists across visits.

```mermaid
sequenceDiagram
    participant U as User (/super)
    participant API as /super/chat/stream
    participant CP as LangGraph checkpointer
    participant RE as Retrieval Engine
    participant LLM as LLM

    U->>API: { message, thread_id }
    API->>CP: load history for thread_id
    alt no ready sources
        API-->>U: SSE error: "No books indexed yet"
    else
        API->>RE: hybrid retrieve across ALL ready source_ids (top_k=8)
        RE-->>API: cross-book chunks
        API->>LLM: system prompt + context + history + message
        LLM-->>U: streamed tokens (SSE)
        API->>API: emit citations, then done
        API->>CP: append turn to history
    end
```
