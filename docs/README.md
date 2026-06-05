# Scholar Documentation

Technical documentation for the Scholar goal-driven AI study system. For a product overview and quick start, see the [root README](../README.md).

## Contents

| Document | What's inside |
|----------|---------------|
| **[scholar-guide.html](scholar-guide.html)** | 📚 **Complete visual guide** — a single self-contained HTML page covering the whole system for KT, demos, and interview prep: architecture, data flow, retrieval, agents, evals, design decisions, a demo script, FAQ, and an interview cheat-sheet. Open it in a browser. |
| **[architecture.md](architecture.md)** | System components, the agent layer, storage model, and a full request map. Start here for the big picture. |
| **[flows.md](flows.md)** | Every important flow as a diagram — ingestion, retrieval routing, the session lifecycle, adaptive follow-ups, the final test, and the Super Agent. |
| **[retrieval.md](retrieval.md)** | Deep dive on the dual retrieval engine: how PageIndex (structural) and vector (semantic) work, when each is used, and how they're merged. |
| **[evaluation.md](evaluation.md)** | How retrieval quality is measured with RAGAS, the evaluation book, the golden Q&A set, the latest results, and how to reproduce them. |
| **[configuration.md](configuration.md)** | The full environment-variable reference — how Scholar stays model-agnostic across providers. |

## System in one paragraph

A **Next.js** frontend talks to a **FastAPI** backend over HTTP + Server-Sent Events. The backend ingests documents into a **dual index** (a PageIndex structural tree on disk + vector embeddings in **pgvector**), and serves a set of **LangGraph**-orchestrated agents (planner, note generator, chat, quiz, adaptive planner, final-test, super agent). Goals, sessions, and chat history live in **SQLite**; conversation state is checkpointed so it survives restarts. Every LLM call is routed through a **provider-agnostic model factory** configured entirely from `.env`.
