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
