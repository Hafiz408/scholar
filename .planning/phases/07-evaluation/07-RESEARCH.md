# Phase 7: Evaluation - Research

**Researched:** 2026-03-19
**Domain:** RAGAS RAG evaluation framework, benchmark scripting, README documentation
**Confidence:** HIGH

## Summary

Phase 7 is the final portfolio artifact phase. Its three requirements (EVAL-01, EVAL-02, EVAL-03) are clearly specified in both the PRD and REQUIREMENTS.md. The work divides into two concrete plans: (1) build the 30-item Q&A dataset and run the RAGAS benchmark against both retrieval strategies, (2) commit JSON results and update the README with a comparison table.

RAGAS 0.2.0 is already pinned in `backend/requirements.txt`. The PRD specifies exact output file naming, metrics (faithfulness, answer_relevancy, context_precision, avg_latency_ms), and README table format. The evaluation directory stub already exists at `backend/eval/` with `golden_qa.json` (empty) and `run_ragas.py` (TODO stub). This phase's main work is filling in those two files plus writing results.

RAGAS 0.2.x has changed its API since 0.1.x. The modern API uses `EvaluationDataset.from_list()` and `ragas.metrics.collections` import paths, not the older `from_dict` / HuggingFace dataset patterns. The `evaluate()` function accepts `EvaluationDataset` directly. Dataset schema uses `user_input`, `retrieved_contexts`, `response`, `reference` (not `question`, `contexts`, `answer`, `ground_truth`).

**Primary recommendation:** Fill `eval/golden_qa.json` with 30 Q&A pairs from OpenStax Biology 2e (free at openstax.org), implement `eval/run_ragas.py` using the RAGAS 0.2 `EvaluationDataset` + `evaluate()` API, run for both PageIndex and vector strategies, commit three JSON files, and update README with the comparison table.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EVAL-01 | RAGAS benchmark run on 30 Q&A pairs from OpenStax Biology 2e (10 deep / 10 broad / 10 intermediate) | RAGAS 0.2 EvaluationDataset API verified; golden_qa.json schema from PRD §14.1; Biology 2e freely available at openstax.org |
| EVAL-02 | Benchmark results committed to eval/results/ as JSON files | Output file naming convention (`pageindex_{ts}.json`, `vector_{ts}.json`, `comparison_{ts}.json`) specified in PRD §14.2; results dir already scaffolded |
| EVAL-03 | README displays RAGAS comparison table (PageIndex vs vector: faithfulness, answer_relevancy, context_precision, avg_latency_ms) | README table format specified verbatim in PRD §14.2; latency measured via time.perf_counter() wrapper around retrieve + generate calls |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ragas | 0.2.0 | RAG evaluation metrics (faithfulness, answer_relevancy, context_precision) | Already pinned in requirements.txt; PRD mandates it |
| langchain-openai | 0.2.14 | LLM and embeddings wrapper for RAGAS evaluator LLM | Already in requirements.txt; RAGAS uses LangchainLLMWrapper |
| openai | 1.58.1 | Direct OpenAI API for embeddings in RAGAS | Already in requirements.txt |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time / datetime | stdlib | Measure avg_latency_ms and generate timestamps for output filenames | Used in run_ragas.py to wrap retrieve+generate calls |
| json | stdlib | Read golden_qa.json, write results JSON files | Standard for all file I/O in eval script |
| argparse | stdlib | `--book-path` CLI arg as specified in PRD §14.2 | Makes script reusable |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ragas 0.2 evaluate() | ragas 0.1 from_dict() + Dataset | 0.1 API deprecated; already on 0.2.0 in requirements.txt |
| gpt-4o-mini as evaluator LLM | gpt-4o | gpt-4o is more capable but costlier; RAGAS evaluator quality with gpt-4o-mini is acceptable for portfolio purposes |

**Installation:** No new packages needed — `ragas==0.2.0` is already in `backend/requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/eval/
├── golden_qa.json          # 30 Q&A pairs (to fill in)
├── run_ragas.py            # eval script (to implement)
└── results/
    ├── pageindex_{ts}.json  # per-question scores + strategy
    ├── vector_{ts}.json     # per-question scores + strategy
    └── comparison_{ts}.json # summary table (goes in README)
```

### Pattern 1: RAGAS 0.2 EvaluationDataset + evaluate()

**What:** Build dataset by running each Q&A pair through the retriever and LLM, collecting inputs/outputs, then calling `evaluate()` once over the full dataset.

**When to use:** Batch evaluation — always preferred over per-question scoring because RAGAS amortizes LLM evaluator overhead.

**Example:**
```python
# Source: https://docs.ragas.io/en/stable/getstarted/rag_eval/
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision
from langchain_openai import ChatOpenAI

evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

# Build dataset records
samples = []
for item in golden_qa:
    contexts, answer, latency_ms = run_retriever_and_generate(item["question"], strategy)
    samples.append({
        "user_input": item["question"],
        "retrieved_contexts": contexts,          # list[str]
        "response": answer,
        "reference": item["ground_truth"],       # needed by ContextPrecision
    })

dataset = EvaluationDataset.from_list(samples)

result = evaluate(
    dataset=dataset,
    metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision()],
    llm=evaluator_llm,
)
# result is an EvaluationResult; result.to_pandas() gives per-row scores
df = result.to_pandas()
scores = {
    "faithfulness": float(df["faithfulness"].mean()),
    "answer_relevancy": float(df["answer_relevancy"].mean()),
    "context_precision": float(df["context_precision"].mean()),
    "avg_latency_ms": float(sum(latencies) / len(latencies)),
}
```

### Pattern 2: Latency Measurement Wrapper

**What:** Wrap the retrieve + generate call with `time.perf_counter()` to capture wall-clock latency per Q&A item.

**When to use:** Whenever avg_latency_ms is required in output (EVAL-03 mandates it).

```python
import time

start = time.perf_counter()
contexts = await retrieve(question, strategy, source_ids)
answer = await generate_answer(question, contexts)
latency_ms = (time.perf_counter() - start) * 1000
```

### Pattern 3: Output File Format

**What:** PRD §14.2 specifies three output files per run.

```python
import datetime, json

ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
results_dir = Path(__file__).parent / "results"
results_dir.mkdir(exist_ok=True)

# Per-strategy detail files
(results_dir / f"pageindex_{ts}.json").write_text(json.dumps(pageindex_output, indent=2))
(results_dir / f"vector_{ts}.json").write_text(json.dumps(vector_output, indent=2))

# Comparison summary
comparison = {
    "run_at": ts,
    "pageindex": pageindex_scores,
    "vector": vector_scores,
}
(results_dir / f"comparison_{ts}.json").write_text(json.dumps(comparison, indent=2))
```

### Pattern 4: golden_qa.json Schema

PRD §14.1 specifies the exact schema:

```json
[
  {
    "id": "q001",
    "question": "How does the sodium-potassium pump maintain resting membrane potential?",
    "ground_truth": "The sodium-potassium pump transports 3 Na⁺ out and 2 K⁺ in per ATP, creating the -70mV resting potential.",
    "question_type": "deep",
    "expected_chapter": "Chapter 35",
    "relevant_pages": [1034, 1035]
  }
]
```

30 items total: 10 `"deep"`, 10 `"broad"`, 10 `"intermediate"`.

### Pattern 5: README Comparison Table

PRD §14.2 specifies exact README table format:

```markdown
| Strategy  | Faithfulness | Answer Relevancy | Context Precision | Avg Latency |
|-----------|-------------|-----------------|-------------------|-------------|
| PageIndex | 0.89        | 0.85            | 0.82              | 1840ms      |
| Vector    | 0.71        | 0.74            | 0.63              | 380ms       |
```

### Anti-Patterns to Avoid

- **Using the RAGAS 0.1 API:** `Dataset.from_dict()` with column names `question`, `contexts`, `answer`, `ground_truth` is the 0.1 schema. RAGAS 0.2 uses `user_input`, `retrieved_contexts`, `response`, `reference`. Wrong column names silently produce NaN scores.
- **Per-question evaluate() calls:** Calling `evaluate()` 30 times (once per item) is 30x slower and 30x more expensive. Build the full EvaluationDataset first, call once.
- **Hardcoding source_id for eval:** The eval script must ingest the Biology 2e PDF first (or use an already-ingested source_id), then pass its ID to the retrievers. Don't embed a hardcoded ID.
- **Missing `reference` for ContextPrecision:** ContextPrecision requires the `reference` field (ground_truth). Omitting it causes a runtime error in RAGAS 0.2.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM-as-judge faithfulness | Custom prompt checking if answer is grounded | `Faithfulness()` from ragas.metrics.collections | RAGAS handles claim extraction, NLI verification, edge cases |
| Answer relevancy scoring | Cosine similarity between question and answer | `AnswerRelevancy()` | RAGAS generates synthetic questions from the answer and compares — non-trivial |
| Context ranking quality | Custom precision@k | `ContextPrecision()` | RAGAS uses LLM to judge relevance of each context chunk against reference |
| Results aggregation | Manual pandas groupby | `result.to_pandas().mean()` | EvaluationResult has built-in conversion |

**Key insight:** RAGAS metrics require multiple LLM calls per sample (claim extraction, NLI, synthetic question generation). Custom implementations routinely miss these sub-steps, producing misleading scores.

---

## Common Pitfalls

### Pitfall 1: RAGAS 0.1 vs 0.2 Column Names

**What goes wrong:** Script writes `question`, `contexts`, `answer`, `ground_truth` into the dataset dict. RAGAS 0.2 expects `user_input`, `retrieved_contexts`, `response`, `reference`. Result: all metric scores are NaN, no error raised.

**Why it happens:** Most tutorials online (including LangFuse, Haystack cookbook) still show the 0.1 API. RAGAS changed the schema in 0.2.

**How to avoid:** Use `EvaluationDataset.from_list()` with the 0.2 column names: `user_input`, `retrieved_contexts` (list[str]), `response`, `reference`.

**Warning signs:** All metric columns in `result.to_pandas()` show NaN.

### Pitfall 2: Biology 2e Not Ingested Before Running Eval

**What goes wrong:** `run_ragas.py --book-path /path/to/bio.pdf` is run but the book hasn't been ingested via the pipeline, so the retriever has no chunks to return.

**Why it happens:** The eval script calls the project's retrievers directly — it depends on the ingestion pipeline having already run and stored chunks in pgvector (and optionally PageIndex).

**How to avoid:** The eval script must either (a) call `run_ingestion()` as a setup step or (b) accept a `--source-id` argument for an already-ingested source. The PRD spec shows `--book-path` suggesting option (a). Make ingestion idempotent (skip if already indexed).

**Warning signs:** Retriever returns zero chunks for every question; faithfulness scores are 0.0 or NaN.

### Pitfall 3: PageIndex Latency Dominates Benchmark

**What goes wrong:** PageIndex retrieval is slow (30-90s per document on first index per PRD §14.2 notes). If the book hasn't been fully indexed, poll timeouts inflate avg_latency_ms for PageIndex to several minutes.

**Why it happens:** PageIndex polling budget is 18×5s = 90s (per STATE.md decision log). If tree isn't ready, retriever blocks.

**How to avoid:** Ensure book is fully ingested and PageIndex tree is confirmed `ready` before starting the benchmark run. Add a preflight check in `run_ragas.py`.

**Warning signs:** First few PageIndex queries take >60s each.

### Pitfall 4: ContextPrecision Requires `reference`

**What goes wrong:** `ContextPrecision()` raises a `ValueError` or returns NaN because `reference` is missing from the dataset rows.

**Why it happens:** ContextPrecision in RAGAS 0.2 is the "with reference" variant by default, needing the ground-truth answer to judge whether retrieved chunks are relevant.

**How to avoid:** Always include `"reference": item["ground_truth"]` in each dataset row. The `golden_qa.json` schema already includes `ground_truth` for this purpose.

### Pitfall 5: Docker Networking for Eval Script

**What goes wrong:** Running `python eval/run_ragas.py` from the host machine fails because `POSTGRES_URL` in `.env` points to `postgresql://scholar:scholar@db:5432/scholar` (container service name), not `localhost`.

**Why it happens:** The backend Dockerfile uses the `db` service name for container-to-container networking. When running eval from the host, the URL must use `localhost:5432`.

**How to avoid:** Use a separate `.env.local` override for eval runs, or run the eval script inside the Docker container: `docker compose exec backend python eval/run_ragas.py --book-path /app/data/uploads/bio2e.pdf`.

---

## Code Examples

Verified patterns from official sources:

### Full run_ragas.py Skeleton

```python
# Source: https://docs.ragas.io/en/stable/getstarted/rag_eval/
# Aligns with PRD §14.2 spec
import argparse, json, time, datetime, asyncio
from pathlib import Path
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision
from langchain_openai import ChatOpenAI

# Import project retriever
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from app.retrieval.hybrid_retriever import retrieve
from app.ingestion.pipeline import run_ingestion
from app.config import settings

RESULTS_DIR = Path(__file__).parent / "results"
GOLDEN_QA_PATH = Path(__file__).parent / "golden_qa.json"


async def run_strategy(golden_qa: list[dict], strategy: str, source_ids: list[str]) -> tuple[dict, list[float]]:
    samples, latencies = [], []
    for item in golden_qa:
        start = time.perf_counter()
        result = await retrieve(item["question"], source_ids, strategy=strategy)
        # Generate answer using LLM (same model as app)
        answer = await generate_answer(item["question"], result.chunks)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
        samples.append({
            "user_input": item["question"],
            "retrieved_contexts": [c.content for c in result.chunks],
            "response": answer,
            "reference": item["ground_truth"],
        })

    dataset = EvaluationDataset.from_list(samples)
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model=settings.llm_model))
    eval_result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision()],
        llm=evaluator_llm,
    )
    df = eval_result.to_pandas()
    scores = {
        "faithfulness": round(float(df["faithfulness"].mean()), 4),
        "answer_relevancy": round(float(df["answer_relevancy"].mean()), 4),
        "context_precision": round(float(df["context_precision"].mean()), 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
        "per_question": df.to_dict(orient="records"),
    }
    return scores, latencies


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-path", required=True, help="Path to OpenStax Biology 2e PDF")
    args = parser.parse_args()

    # Ingest book if not already done
    source_id = await ensure_ingested(args.book_path)
    source_ids = [source_id]

    golden_qa = json.loads(GOLDEN_QA_PATH.read_text())
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    RESULTS_DIR.mkdir(exist_ok=True)

    pageindex_scores, _ = await run_strategy(golden_qa, "pageindex", source_ids)
    vector_scores, _ = await run_strategy(golden_qa, "vector", source_ids)

    (RESULTS_DIR / f"pageindex_{ts}.json").write_text(json.dumps(pageindex_scores, indent=2))
    (RESULTS_DIR / f"vector_{ts}.json").write_text(json.dumps(vector_scores, indent=2))

    comparison = {
        "run_at": ts,
        "pageindex": {k: v for k, v in pageindex_scores.items() if k != "per_question"},
        "vector": {k: v for k, v in vector_scores.items() if k != "per_question"},
    }
    (RESULTS_DIR / f"comparison_{ts}.json").write_text(json.dumps(comparison, indent=2))
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
```

### Importing RAGAS 0.2 Metrics (Verified)

```python
# Source: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
# Source: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/
# Source: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Dataset.from_dict({"question": ..., "contexts": ..., "answer": ..., "ground_truth": ...})` | `EvaluationDataset.from_list([{"user_input": ..., "retrieved_contexts": ..., "response": ..., "reference": ...}])` | RAGAS 0.2.0 | Column names changed; wrong names produce silent NaN, not an error |
| `from ragas.metrics import faithfulness` (0.1) | `from ragas.metrics.collections import Faithfulness` (0.2) | RAGAS 0.2.0 | Import path changed; old path still works as alias in 0.2.0 but deprecated |
| `evaluate()` is primary API | `@experiment` decorator is the preferred new pattern | RAGAS 0.2+ | `evaluate()` still works and is simpler for scripting; `@experiment` is for production pipelines |

**Deprecated/outdated:**
- `from ragas.metrics import faithfulness` (lowercase singleton): works in 0.2.0 as compatibility shim but deprecated; use class-based `Faithfulness()`.
- `Dataset` (HuggingFace datasets): works via `column_map` but adds unnecessary dependency; use `EvaluationDataset.from_list()`.

---

## Open Questions

1. **PageIndex availability at eval time**
   - What we know: PageIndex tree build takes 30-90s per document; eval depends on a fully indexed source.
   - What's unclear: Whether the Biology 2e PDF will be available at the time Phase 7 executes (user must provide it).
   - Recommendation: Plan should include a setup step that downloads or provides the Biology 2e PDF and confirms PageIndex indexing is complete before benchmark runs.

2. **Running eval inside Docker vs. on host**
   - What we know: `POSTGRES_URL` uses `db` service name inside Docker, `localhost` outside.
   - What's unclear: How the user will actually invoke `run_ragas.py` in their environment.
   - Recommendation: Plan tasks around running via `docker compose exec backend python eval/run_ragas.py --book-path /app/data/uploads/bio2e.pdf` to avoid networking issues.

3. **RAGAS evaluator LLM cost**
   - What we know: 30 Q&A pairs × 2 strategies = 60 eval runs; each RAGAS metric requires 1-3 LLM calls.
   - What's unclear: Exact token cost with gpt-4o-mini.
   - Recommendation: Estimate ~$0.50-1.50 total with gpt-4o-mini. Acceptable for portfolio use; document in plan.

---

## Sources

### Primary (HIGH confidence)

- https://docs.ragas.io/en/stable/getstarted/rag_eval/ — EvaluationDataset.from_list(), evaluate() usage
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/ — Faithfulness import path, required fields
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/ — AnswerRelevancy import path, required fields
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/ — ContextPrecision import path, required `reference` field
- https://docs.ragas.io/en/stable/references/evaluate/ — evaluate() function signature
- `/Users/mohammedhafiz/Desktop/Personal/scholar/scholar_v1_prd.md` §14 — golden_qa.json schema, run_ragas.py spec, README table format
- `/Users/mohammedhafiz/Desktop/Personal/scholar/backend/requirements.txt` — confirmed ragas==0.2.0 already installed

### Secondary (MEDIUM confidence)

- https://openstax.org/details/books/biology-2e — Biology 2e freely available (CC BY); PDF download confirmed
- https://archive.org/details/Biology2e — Internet Archive backup copy of Biology 2e

### Tertiary (LOW confidence)

- Community blogs (langfuse.com, cohorte.co) — confirmed RAGAS 0.1 vs 0.2 API differences, but tutorials lag official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — ragas==0.2.0 already in requirements.txt; PRD fully specifies output format
- Architecture: HIGH — PRD §14 is prescriptive; eval/ stub exists; RAGAS 0.2 API verified against official docs
- Pitfalls: MEDIUM — Column name change (0.1→0.2) verified; Docker networking pitfall is inferred from project setup

**Research date:** 2026-03-19
**Valid until:** 2026-04-18 (RAGAS 0.2.x is stable; 30 days is conservative)
