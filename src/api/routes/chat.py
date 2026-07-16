"""Agent chat route - single entry point backed by the LangGraph supervisor.

Exposes the full multi-agent system (supervisor -> mentor / rag / planner /
evaluator / current-affairs) behind one authenticated endpoint. Each request
runs on a per-user thread so the checkpointer can persist conversation state and
the long-term store can personalise responses.

The handler is intentionally a synchronous ``def``: the compiled graph uses a
synchronous Postgres checkpointer, so it must be invoked with ``.invoke``.
FastAPI runs sync handlers in a worker thread, so the event loop is never
blocked.

Both endpoints consult an optional Upstash-backed response cache
(``src.core.response_cache``): a cache hit returns the stored answer without
re-running the agent graph, cutting latency and LLM cost on repeated/retried
questions. The cache is a no-op unless configured, so behaviour is unchanged by
default.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.core.response_cache import get_response_cache
from src.graph.app_graph import make_config
from src.graph.memory import get_store, load_student_profile, save_student_profile
from src.graph.profile import extract_student_profile_signals, merge_student_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    thread_id: str | None = Field(
        default=None,
        description="Conversation/session id. Defaults to a per-user thread.",
    )


def _learn_from_question(store, user_id: str, profile: dict, question: str) -> None:
    """Update the long-term student profile from the raw question.

    Runs on both cache hits and misses so personalisation keeps learning even
    when the answer itself was served from cache.
    """
    updates = extract_student_profile_signals(question)
    if updates:
        save_student_profile(store, user_id, merge_student_profile(profile, updates))


# Nodes that emit the final, user-facing answer. Streaming is filtered to these
# so internal routing/grading LLM calls never leak into the response stream.
# "agent" is the canonical mentor tool-calling brain's answer node; its
# tool-deciding turns carry no content, so only the final answer streams.
_FINAL_NODES = {"generate", "planner", "evaluator", "current_affairs", "agent"}


def _chunk_text(content) -> str:
    """Normalise a message chunk's ``content`` to plain text.

    Most chat models yield string content, but some emit a list of content
    parts (e.g. multimodal blocks); flatten those to their text payloads.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for piece in content:
            if isinstance(piece, dict):
                parts.append(piece.get("text", ""))
            else:
                parts.append(str(piece))
        return "".join(parts)
    return str(content or "")


def _iter_chunks(text: str, size: int = 120):
    """Yield a cached answer in small slices so a cache hit still streams
    smoothly to the client instead of arriving as one large blob."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


@router.post("/chat/stream")
def agent_chat_stream(
    payload: AgentChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """Stream the supervisor graph's final answer token-by-token.

    Runs the graph with ``stream_mode=["messages", "values"]`` so answer tokens
    can be forwarded as they are generated, while the final state is retained as
    a fallback for routes whose generation is not token-streamable. Token output
    is filtered to the answer-producing nodes so internal routing and grading
    LLM calls never leak into the user-facing stream.

    A cache hit streams the stored answer in small slices (still smooth for the
    client) without touching the graph.
    """
    agent_graph = getattr(request.app.state, "agent_graph", None)
    if agent_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent graph is not ready",
        )

    user_id = user["id"]
    # Default to one stable thread per user so the checkpointer persists
    # conversation memory across sessions; clients may pass an explicit thread_id.
    thread_id = payload.thread_id or f"{user_id}:default"
    config = make_config(thread_id=thread_id, user_id=user_id)
    store = get_store()
    profile = load_student_profile(store, user_id)
    cache = get_response_cache()

    def generate():
        # Fast path: serve a cached answer without running the graph.
        cached = cache.get(user_id=user_id, thread_id=thread_id, question=payload.question)
        if cached is not None:
            for piece in _iter_chunks(cached.get("answer") or ""):
                yield piece
            _learn_from_question(store, user_id, profile, payload.question)
            return

        streamed = False
        final_answer = ""
        buffer = []
        try:
            for mode, data in agent_graph.stream(
                {"question": payload.question, "student_context": profile},
                config,
                stream_mode=["messages", "values"],
            ):
                if mode == "messages":
                    chunk, metadata = data
                    if metadata.get("langgraph_node") in _FINAL_NODES:
                        text = _chunk_text(getattr(chunk, "content", ""))
                        if text:
                            streamed = True
                            buffer.append(text)
                            yield text
                elif mode == "values" and isinstance(data, dict):
                    if data.get("answer"):
                        final_answer = data["answer"]
        except Exception:
            logger.exception("Agent stream invocation failed")
            yield "\n\n\u26a0\ufe0f Sorry, the agent hit an error. Please try again."
            return
        # Fallback: if a route did not stream any tokens, emit the final answer
        # captured from graph state so the user always receives a response.
        if not streamed and final_answer:
            yield final_answer

        answer = ("".join(buffer)).strip() or final_answer
        _learn_from_question(store, user_id, profile, payload.question)
        if answer:
            cache.set(
                user_id=user_id,
                thread_id=thread_id,
                question=payload.question,
                answer=answer,
            )

    return StreamingResponse(generate(), media_type="text/plain")
