"""Agent chat route - single entry point backed by the LangGraph supervisor.

Exposes the full multi-agent system (supervisor -> mentor / rag / planner /
evaluator / current-affairs) behind one authenticated endpoint. Each request
runs on a per-user thread so the checkpointer can persist conversation state and
the long-term store can personalise responses.

The handler is intentionally a synchronous ``def``: the compiled graph uses a
synchronous Postgres checkpointer, so it must be invoked with ``.invoke``.
FastAPI runs sync handlers in a worker thread, so the event loop is never
blocked.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.graph.app_graph import make_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    thread_id: str | None = Field(
        default=None,
        description="Conversation/session id. Defaults to a per-user thread.",
    )


class AgentChatResponse(BaseModel):
    response: str
    route: str | None = None


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(
    payload: AgentChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> AgentChatResponse:
    """Route a question through the supervisor graph and return the answer."""
    agent_graph = getattr(request.app.state, "agent_graph", None)
    if agent_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent graph is not ready",
        )

    user_id = user["id"]
    # Default to one stable thread per user; clients may pass an explicit
    # thread_id to keep multiple independent conversations.
    thread_id = payload.thread_id or f"{user_id}:default"
    config = make_config(thread_id=thread_id, user_id=user_id)

    try:
        result = agent_graph.invoke({"question": payload.question}, config)
    except Exception:
        logger.exception("Agent graph invocation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent failed to generate a response",
        )

    return AgentChatResponse(
        response=result.get("answer") or "",
        route=result.get("route"),
    )


# Nodes that emit the final, user-facing answer. Streaming is filtered to these
# so internal routing/grading LLM calls never leak into the response stream.
_FINAL_NODES = {"generate", "planner", "evaluator", "current_affairs"}


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

    def generate():
        streamed = False
        final_answer = ""
        try:
            for mode, data in agent_graph.stream(
                {"question": payload.question},
                config,
                stream_mode=["messages", "values"],
            ):
                if mode == "messages":
                    chunk, metadata = data
                    if metadata.get("langgraph_node") in _FINAL_NODES:
                        text = _chunk_text(getattr(chunk, "content", ""))
                        if text:
                            streamed = True
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

    return StreamingResponse(generate(), media_type="text/plain")
