"""RAGAS 0.2 benchmark script for Scholar dual retrieval engine evaluation.

Usage (inside Docker container):
    docker compose exec backend python eval/run_ragas.py --book-path /app/data/uploads/bio2e.pdf
    docker compose exec backend python eval/run_ragas.py --book-path /app/data/uploads/bio2e.pdf --dry-run

Evaluates both retrieval strategies (pageindex and vector) against the 30-item
golden Q&A dataset in golden_qa.json, writing three JSON result files to eval/results/.
"""

import argparse
import asyncio
import datetime
import json
import logging
import sys
import time
from pathlib import Path
from time import perf_counter

# Allow imports from backend/ when script is run from eval/
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
import openai
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision, Faithfulness
from langchain_openai import ChatOpenAI

from app.config import settings
from app.ingestion.pipeline import run_ingestion
from app.retrieval.hybrid_retriever import _get_sources_with_pageindex
from app.retrieval.pageindex_retriever import fetch_pageindex_chunks
from app.retrieval.vector_retriever import vector_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

GOLDEN_QA_PATH = Path(__file__).parent / "golden_qa.json"
RESULTS_DIR = Path(__file__).parent / "results"

TOP_K = 5
INGESTION_POLL_INTERVAL_S = 5
INGESTION_TIMEOUT_S = 120


# ---------------------------------------------------------------------------
# Idempotent ingestion
# ---------------------------------------------------------------------------


async def ensure_ingested(book_path: str) -> str:
    """Ingest the PDF if not already indexed; return its source_id.

    Checks the knowledge_sources SQLite table for an existing entry with the
    same file_path or title (derived from filename). If status == "ready",
    returns the source_id immediately. Otherwise, triggers run_ingestion and
    polls until ready (max INGESTION_TIMEOUT_S seconds).

    Args:
        book_path: Absolute path to the PDF file to ingest.

    Returns:
        source_id string for the ingested source.

    Raises:
        RuntimeError: If ingestion does not complete within the timeout.
    """
    import uuid
    import os

    filename = os.path.basename(book_path)

    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if already ingested by file_path or filename-in-title
        row = await (
            await db.execute(
                "SELECT id, status FROM knowledge_sources WHERE file_path = ? OR title LIKE ? LIMIT 1",
                (book_path, f"%{filename}%"),
            )
        ).fetchone()

        if row and row["status"] == "ready":
            source_id = row["id"]
            logger.info("Source already ingested: source_id=%s", source_id)
            return source_id

        if row:
            source_id = row["id"]
            logger.info(
                "Source found but status=%s; waiting for completion (source_id=%s)",
                row["status"],
                source_id,
            )
        else:
            # Create knowledge_sources row and kick off ingestion
            source_id = str(uuid.uuid4())
            title = filename.replace("_", " ").replace("-", " ").rsplit(".", 1)[0]
            import datetime as _dt

            created_at = _dt.datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO knowledge_sources (id, title, source_type, file_path, status, created_at) "
                "VALUES (?, ?, 'pdf', ?, 'pending', ?)",
                (source_id, title, book_path, created_at),
            )
            await db.commit()
            logger.info("Starting ingestion: source_id=%s path=%s", source_id, book_path)
            # run_ingestion manages its own aiosqlite connection internally
            asyncio.create_task(
                run_ingestion(
                    source_id=source_id,
                    file_path=book_path,
                    url=None,
                    source_type="pdf",
                    title=title,
                )
            )

    # Poll until status == "ready"
    deadline = time.monotonic() + INGESTION_TIMEOUT_S
    while time.monotonic() < deadline:
        await asyncio.sleep(INGESTION_POLL_INTERVAL_S)
        async with aiosqlite.connect(settings.sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT status FROM knowledge_sources WHERE id = ?", (source_id,)
                )
            ).fetchone()
        if row and row["status"] == "ready":
            logger.info("Ingestion complete: source_id=%s", source_id)
            return source_id
        if row and row["status"] == "failed":
            raise RuntimeError(f"Ingestion failed for source_id={source_id}")
        logger.info("Ingestion in progress (status=%s)...", row["status"] if row else "unknown")

    raise RuntimeError(
        f"Ingestion timed out after {INGESTION_TIMEOUT_S}s for source_id={source_id}"
    )


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------


async def generate_answer(question: str, chunks: list) -> str:
    """Generate an answer using gpt-4o-mini given retrieved chunks as context.

    Args:
        question: The question to answer.
        chunks: List of RetrievedChunk objects whose .content will be used as context.

    Returns:
        Generated answer string.
    """
    context = "\n\n".join(chunk.content for chunk in chunks) if chunks else "(no context retrieved)"
    client = openai.AsyncOpenAI(
        api_key=settings.llm_api_key or settings.openai_api_key or None,
            base_url=settings.llm_base_url or None,
    )
    response = await client.chat.completions.create(
        model=settings.llm_model or "gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful study assistant. Answer the question using ONLY the "
                    "provided context. If the context does not contain enough information, say so."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Per-strategy benchmark runner
# ---------------------------------------------------------------------------


async def run_strategy(
    golden_qa: list,
    strategy: str,
    source_ids: list[str],
    evaluator_llm,
    dry_run: bool = False,
) -> dict:
    """Run the full benchmark for a single retrieval strategy.

    Iterates over all golden_qa items, calls the appropriate retriever directly
    to force the specified strategy (bypassing the query router), generates answers,
    then runs RAGAS evaluation once over the full dataset.

    Args:
        golden_qa: List of 30 Q&A item dicts from golden_qa.json.
        strategy: Either "pageindex" or "vector".
        source_ids: List of knowledge source UUIDs to query against.
        evaluator_llm: LangchainLLMWrapper for RAGAS evaluation.
        dry_run: If True, skip actual evaluate() call and use mock scores.

    Returns:
        Dict with keys: faithfulness, answer_relevancy, context_precision,
        avg_latency_ms, per_question (list of per-item result dicts).
    """
    samples = []
    latencies_ms = []

    # Resolve pageindex sources once (needed only for "pageindex" strategy)
    pi_sources: list[tuple[str, str, str]] = []
    if strategy == "pageindex":
        pi_sources = await _get_sources_with_pageindex(source_ids)
        if not pi_sources:
            logger.warning(
                "No sources with pageindex_doc_id found — pageindex strategy will return empty chunks"
            )

    logger.info("Running %s strategy over %d questions...", strategy, len(golden_qa))

    for item in golden_qa:
        question = item["question"]
        t0 = perf_counter()

        if strategy == "pageindex":
            # Fetch from all pageindex sources concurrently
            if pi_sources:
                tasks = [
                    fetch_pageindex_chunks(doc_id, question, sid, stitle, top_k=TOP_K)
                    for doc_id, sid, stitle in pi_sources
                ]
                results = await asyncio.gather(*tasks)
                chunks = [c for result in results for c in result]
                # Sort by relevance_score and take top-k
                chunks = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)[:TOP_K]
            else:
                chunks = []
        else:
            # vector strategy
            chunks = await vector_search(question, source_ids, top_k=TOP_K)

        answer = await generate_answer(question, chunks)
        latency_ms = int((perf_counter() - t0) * 1000)
        latencies_ms.append(latency_ms)

        # RAGAS 0.2 column names: user_input, retrieved_contexts, response, reference
        sample = {
            "user_input": question,
            "retrieved_contexts": [chunk.content for chunk in chunks],
            "response": answer,
            "reference": item["ground_truth"],
        }
        samples.append(sample)

        logger.info(
            "  [%s] %s — %d chunks, %d ms",
            item["id"],
            question[:60],
            len(chunks),
            latency_ms,
        )

    avg_latency_ms = int(sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0

    if dry_run:
        logger.info("--dry-run: skipping RAGAS evaluate() call, using mock scores")
        per_question = [
            {
                "user_input": s["user_input"],
                "faithfulness": 0.5,
                "answer_relevancy": 0.5,
                "context_precision": 0.5,
            }
            for s in samples
        ]
        return {
            "faithfulness": 0.5,
            "answer_relevancy": 0.5,
            "context_precision": 0.5,
            "avg_latency_ms": avg_latency_ms,
            "per_question": per_question,
        }

    # Build RAGAS 0.2 EvaluationDataset from all samples at once
    dataset = EvaluationDataset.from_list(samples)

    logger.info("Running RAGAS evaluate() for %s strategy...", strategy)
    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision()],
        llm=evaluator_llm,
    )

    df = result.to_pandas()
    per_question = df.to_dict(orient="records")

    scores = {
        "faithfulness": float(df["faithfulness"].mean()) if "faithfulness" in df.columns else None,
        "answer_relevancy": float(df["answer_relevancy"].mean()) if "answer_relevancy" in df.columns else None,
        "context_precision": float(df["context_precision"].mean()) if "context_precision" in df.columns else None,
        "avg_latency_ms": avg_latency_ms,
        "per_question": per_question,
    }

    logger.info(
        "%s results — faithfulness=%.3f  answer_relevancy=%.3f  context_precision=%.3f  avg_latency=%dms",
        strategy,
        scores["faithfulness"] or 0,
        scores["answer_relevancy"] or 0,
        scores["context_precision"] or 0,
        avg_latency_ms,
    )

    return scores


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAGAS 0.2 benchmark for Scholar dual retrieval engine"
    )
    parser.add_argument(
        "--book-path",
        required=True,
        help="Absolute path to the PDF to benchmark (e.g. /app/data/uploads/bio2e.pdf)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Skip RAGAS evaluate() call and write mock scores (0.5) — useful for testing script structure",
    )
    args = parser.parse_args()

    # Step 1: Idempotent ingestion
    logger.info("Ensuring PDF is ingested: %s", args.book_path)
    source_id = await ensure_ingested(args.book_path)
    source_ids = [source_id]

    # Step 2: Preflight — check pageindex availability
    pi_sources = await _get_sources_with_pageindex(source_ids)
    if pi_sources:
        logger.info(
            "Preflight: pageindex_doc_id found for %d source(s) — pageindex strategy available",
            len(pi_sources),
        )
    else:
        logger.warning(
            "Preflight: no pageindex_doc_id found — pageindex strategy will return empty chunks"
        )

    # Step 3: Load golden Q&A dataset
    with open(GOLDEN_QA_PATH) as f:
        golden_qa = json.load(f)
    logger.info("Loaded %d golden Q&A pairs from %s", len(golden_qa), GOLDEN_QA_PATH)

    # Step 4: Initialise RAGAS evaluator LLM
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key or settings.openai_api_key or None,
            base_url=settings.llm_base_url or None,
        )
    )

    # Step 5: Prepare results directory and timestamp
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")

    # Step 6: Run pageindex strategy
    logger.info("=== pageindex strategy ===")
    pi_scores = await run_strategy(
        golden_qa=golden_qa,
        strategy="pageindex",
        source_ids=source_ids,
        evaluator_llm=evaluator_llm,
        dry_run=args.dry_run,
    )
    pi_path = RESULTS_DIR / f"pageindex_{ts}.json"
    with open(pi_path, "w") as f:
        json.dump(pi_scores, f, indent=2, default=str)
    logger.info("Wrote pageindex results to %s", pi_path)

    # Step 7: Run vector strategy
    logger.info("=== vector strategy ===")
    vec_scores = await run_strategy(
        golden_qa=golden_qa,
        strategy="vector",
        source_ids=source_ids,
        evaluator_llm=evaluator_llm,
        dry_run=args.dry_run,
    )
    vec_path = RESULTS_DIR / f"vector_{ts}.json"
    with open(vec_path, "w") as f:
        json.dump(vec_scores, f, indent=2, default=str)
    logger.info("Wrote vector results to %s", vec_path)

    # Step 8: Build and write comparison (summary without per_question)
    comparison = {
        "run_at": ts,
        "pageindex": {k: v for k, v in pi_scores.items() if k != "per_question"},
        "vector": {k: v for k, v in vec_scores.items() if k != "per_question"},
    }
    cmp_path = RESULTS_DIR / f"comparison_{ts}.json"
    with open(cmp_path, "w") as f:
        json.dump(comparison, f, indent=2, default=str)
    logger.info("Wrote comparison to %s", cmp_path)

    # Step 9: Print comparison to stdout
    print("\n=== Benchmark Comparison ===")
    print(json.dumps(comparison, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
