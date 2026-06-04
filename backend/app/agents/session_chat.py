import json
import asyncio
import logging
import time
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.llm_factory import get_llm
from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.retrieval.hybrid_retriever import retrieve

logger = logging.getLogger(__name__)


def _format_context(chunks) -> str:
    """Format RetrievedChunk list into numbered context block."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = getattr(chunk, "source_title", "Unknown Source")
        page = getattr(chunk, "page_number", "?")
        parts.append(f"[{i}] (Source: {source}, p.{page})\n{chunk.content}")
    return "\n\n".join(parts)


async def stream_chat(
    session_id: str,
    goal_id: str,
    message: str,
    source_ids: list[str],
    checkpointer: AsyncSqliteSaver,
):
    """Async generator yielding SSE-formatted strings for chat responses."""
    try:
        retrieval = await retrieve(message, source_ids, top_k=5)
        context = _format_context(retrieval.chunks)

        # Load existing chat history from LangGraph checkpointer
        # checkpoint_ns is required by AsyncSqliteSaver.aput(); empty string is the
        # default namespace. Omitting it raises KeyError: 'checkpoint_ns' on save.
        config = {"configurable": {"thread_id": goal_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)

        history: list[dict] = []
        if checkpoint_tuple and checkpoint_tuple.checkpoint:
            # Extract messages from checkpoint state
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
            "channel_values": {"messages": updated_messages, "goal_id": goal_id},
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
    except Exception as exc:
        logger.exception("Chat stream failed for session %s", session_id)
        payload = json.dumps({"type": "error", "content": str(exc)})
        yield f"event: error\ndata: {payload}\n\n"
