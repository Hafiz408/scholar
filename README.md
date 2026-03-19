# Scholar V1

**Goal-Driven AI Study System** — Upload textbooks, set a study goal, get a multi-session plan, work through sessions with AI-generated notes, grounded chat, and quizzes.

## Architecture

Scholar uses a **dual retrieval engine**:
- **PageIndex** — vectorless, reasoning-based retrieval for deep within-book structural questions
- **pgvector** — cross-book semantic search via OpenAI embeddings
- **Router agent** — classifies each query and picks the optimal retrieval strategy

The LangGraph orchestrator manages the study lifecycle: Planner → Session (Notes + Chat + Quiz) → Complete.

## Quick Start

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, PAGEINDEX_API_KEY, LANGCHAIN_API_KEY
docker compose up
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + LangChain + LangGraph |
| Observability | LangSmith |
| Vector Store | pgvector (PostgreSQL) |
| PageIndex | pageindex Python client |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | gpt-4o-mini |
| State Persistence | LangGraph SqliteSaver |
| Frontend | Next.js 14 + TypeScript + Tailwind |

## Evaluation

RAGAS benchmark comparing PageIndex vs vector RAG on 30 Q&A pairs from OpenStax Biology 2e:

| Strategy  | Faithfulness | Answer Relevancy | Context Precision | Avg Latency |
|-----------|-------------|-----------------|-------------------|-------------|
| PageIndex | 0.50 | 0.50 | 0.50 | 0ms |
| Vector    | 0.50 | 0.50 | 0.50 | 0ms |

*Scores shown are dry-run placeholders. Run `eval/run_ragas.py --book-path /app/data/uploads/bio2e.pdf` with the OpenStax Biology 2e PDF for real benchmark scores.*

## Running Tests

```bash
cd backend
pytest tests/ -v
```
