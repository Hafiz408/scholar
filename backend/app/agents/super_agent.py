import json
import asyncio
from app.core.logging import get_logger
import time
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core import pg
from app.core.llm_factory import get_llm
from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.retrieval.hybrid_retriever import retrieve

logger = get_logger(__name__)


def _format_context(chunks) -> str:
    """Format RetrievedChunk list into numbered context block."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = getattr(chunk, "source_title", "Unknown Source")
        page = getattr(chunk, "page_number", "?")
        parts.append(f"[{i}] (Source: {source}, p.{page})\n{chunk.content}")
    return "\n\n".join(parts)


async def stream_super_chat(
    message: str,
    thread_id: str,
    checkpointer: AsyncSqliteSaver,
):
    """Async generator yielding SSE-formatted strings for cross-source super chat responses.

    Retrieves context from ALL ready knowledge sources (not scoped to any goal/session).
    Uses the caller-provided thread_id as the LangGraph checkpoint key — server never
    generates or overrides it.
    """
    try:
        # Query ALL ready knowledge sources (SUP-01)
        async with pg.connect() as db:
            async with db.execute(
                "SELECT id FROM knowledge_sources WHERE status = 'ready'"
            ) as cur:
                rows = await cur.fetchall()
        source_ids = [row["id"] for row in rows]

        # Empty-sources guard (SUP-02)
        if not source_ids:
            payload = json.dumps({"type": "error", "content": "No books indexed yet"})
            yield f"event: error\ndata: {payload}\n\n"
            return

        # Retrieve with top_k=8 (larger source pool warrants more chunks)
        retrieval = await retrieve(message, source_ids, top_k=8)
        context = _format_context(retrieval.chunks)

        # Load existing chat history from LangGraph checkpointer (SUP-03)
        # thread_id comes from the caller — never generated server-side
        # checkpoint_ns is required by AsyncSqliteSaver.aput(); empty string is the
        # default namespace. Omitting it raises KeyError: 'checkpoint_ns' on save.
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)

        history: list[dict] = []
        if checkpoint_tuple and checkpoint_tuple.checkpoint:
            state_messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            history = list(state_messages)

        system_msg = {"role": "system", "content": CHAT_SYSTEM_PROMPT.format(context=context)}
        user_msg = {"role": "user", "content": message}

        llm = get_llm(temperature=0, streaming=True)
        all_messages = [system_msg, *history, user_msg]

        full_response: list[str] = []
        async for chunk in llm.astream(all_messages):
            token = chunk.content
            if token:
                full_response.append(token)
                payload = json.dumps({"type": "token", "content": token})
                yield f"event: token\ndata: {payload}\n\n"

        assistant_content = "".join(full_response)

        # Save updated history to LangGraph checkpointer
        updated_messages = list(history) + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_content},
        ]

        # Build minimal checkpoint for history persistence
        # Note: no goal_id field — super chat is not goal-scoped
        try:
            from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
        except ImportError:
            try:
                from langgraph.checkpoint.types import Checkpoint, CheckpointMetadata
            except ImportError:
                Checkpoint = dict
                CheckpointMetadata = dict

        new_checkpoint = {
            "v": 1,
            "id": str(int(time.time() * 1000)),
            "ts": "",
            "channel_values": {"messages": updated_messages},
            "channel_versions": {},
            "versions_seen": {},
            "pending_sends": [],
        }
        metadata = {"source": "update", "step": len(updated_messages), "writes": {}}
        await checkpointer.aput(config, new_checkpoint, metadata, {})

        # Send citations event
        citations_payload = json.dumps({
            "type": "citations",
            "chunks": [
                {
                    "content": c.content[:200],
                    "source_title": getattr(c, "source_title", ""),
                    "page_number": getattr(c, "page_number", None),
                }
                for c in retrieval.chunks
            ],
        })
        yield f"event: citations\ndata: {citations_payload}\n\n"

        done_payload = json.dumps({
            "type": "done",
            "strategy_used": getattr(retrieval, "strategy_used", ""),
            "latency_ms": getattr(retrieval, "latency_ms", 0),
        })
        yield f"event: done\ndata: {done_payload}\n\n"

    except asyncio.CancelledError:
        return
    except Exception as e:
        # The error event already informs the client; re-raising after the response
        # body has started streaming only surfaces as a noisy ASGI exception.
        logger.exception("Super chat stream failed for thread %s", thread_id)
        payload = json.dumps({"type": "error", "content": str(e)})
        yield f"event: error\ndata: {payload}\n\n"
