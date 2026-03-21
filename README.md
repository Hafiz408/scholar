# Scholar V1

**Goal-Driven AI Study System** — Upload textbooks, set a study goal, get a multi-session study plan, then work through each session with AI-generated notes, grounded chat, and quizzes.

## How It Works

1. **Upload** a PDF textbook or URL → Scholar ingests it into both a PageIndex tree and a pgvector embedding store
2. **Set a goal** → the Planner agent generates a sequenced multi-session study plan
3. **Work a session** → AI streams notes grounded in your book, chat answers questions with citations, quiz tests your understanding

## Architecture

Scholar uses a **dual retrieval engine** — every chat message is routed to the best strategy:

| Strategy | How | Best for |
|----------|-----|---------|
| **PageIndex** | LLM navigates a hierarchical JSON tree of the document | Chapter/section questions, long-form context |
| **Vector RAG** | Cosine similarity over pgvector embeddings | Factual lookups, cross-book search |
| **Hybrid** | Both concurrently, merged 0.6/0.4 by score | Complex questions needing both depth and breadth |

A **Router agent** classifies each query and picks the strategy. If no PageIndex tree exists, it falls back to vector automatically.

→ Full architecture, flow diagrams, and component details: **[docs/architecture.md](docs/architecture.md)**

## Quick Start

```bash
cp backend/.env.example backend/.env
# Fill in LLM_API_KEY, EMBEDDING_API_KEY (Mistral or OpenAI)
docker compose up
```

- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

## Configuration

```env
# LLM — Mistral (free tier) or OpenAI
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.mistral.ai/v1   # empty = OpenAI
LLM_MODEL=mistral-small-latest

# Embeddings
EMBEDDING_API_KEY=your-key
EMBEDDING_BASE_URL=https://api.mistral.ai/v1
EMBEDDING_MODEL=mistral-embed
EMBEDDING_DIMENSIONS=1024
```

PageIndex uses the same `LLM_*` settings automatically — no separate key needed.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + LangChain + LangGraph |
| Vector store | PostgreSQL + pgvector |
| Document tree | PageIndex (open-source, local library) |
| Embeddings | OpenAI / Mistral compatible |
| State & chat history | LangGraph AsyncSqliteSaver (SQLite) |
| Observability | LangSmith |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |

## Running Tests

```bash
# Run all tests inside Docker (recommended)
docker compose exec backend pytest tests/ -v

# Or locally (requires backend deps installed)
cd backend && pytest tests/ -v
```

49/50 tests pass. One test (`test_router_accuracy_gate`) requires a live LLM API key.

## Evaluation

RAGAS benchmark comparing PageIndex vs vector RAG on 30 Q&A pairs:

| Strategy | Faithfulness | Answer Relevancy | Context Precision | Avg Latency |
|----------|-------------|-----------------|-------------------|-------------|
| PageIndex | 0.64 | N/A† | 0.00 | 1592ms |
| Vector | 0.54 | N/A† | 0.00 | 1373ms |

*Scores from real RAGAS benchmark run (30 Q&A pairs). † Answer Relevancy requires an OpenAI API key for embedding-based scoring (not configured). Context Precision is 0.00 because the pgvector store was empty during this run — re-run after a full PDF ingestion with PageIndex tree for representative scores. Run the benchmark:*

```bash
docker compose exec backend python eval/run_ragas.py \
  --book-path /app/data/uploads/your-book.pdf \
  --output-dir eval/results/
```

## Project Structure

```
scholar/
├── backend/
│   ├── app/
│   │   ├── ingestion/        # pdf_extractor, url_extractor, embedder, pageindex_builder, pipeline
│   │   ├── retrieval/        # router, vector_retriever, pageindex_retriever, hybrid_retriever
│   │   ├── agents/           # planner, note_generator, session_chat, quiz_agent, orchestrator
│   │   ├── routers/          # FastAPI routes: knowledge, goals, sessions, chat, quiz
│   │   └── models/           # Pydantic schemas
│   ├── eval/                 # golden_qa.json + run_ragas.py benchmark
│   └── tests/                # pytest test suite (49/50 passing)
├── frontend/                 # Next.js 14 app
└── docs/                     # Architecture diagrams and design docs
```
