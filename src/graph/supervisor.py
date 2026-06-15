"""Top-level supervisor graph (hierarchical router).

The supervisor classifies a free-text message into one specialist and dispatches
to the matching subgraph. All subgraphs share ``AgentState``, so they are nested
directly as nodes. Only the supervisor is compiled with a checkpointer/store;
nested subgraphs inherit memory through the shared state.

Routing:
    mentor           General doubts, concept explanations, advice, motivation, chat.
    planner          Create / revise a study plan or timetable.
    evaluator        Check, grade, or evaluate a written answer.
    current_affairs  Daily / monthly current affairs, news, editorials.
    rag              Questions about a specific document (NCERT / lecture / upload / PYQ).

Form-style specialists (planner / evaluator / current_affairs) read their
structured parameters from ``state['task_inputs']``; rag additionally needs
``state['persist_key']``. A caller may also force a route by pre-setting
``state['route']`` (e.g. when the UI already knows the target).
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.core.llm import get_fast_llm
from src.graph.mentor_graph import build_mentor_graph
from src.graph.rag_graph import build_rag_subgraph
from src.graph.agent_subgraphs import (
    build_planner_subgraph,
    build_evaluator_subgraph,
    build_current_affairs_subgraph,
)

logger = logging.getLogger(__name__)

_ROUTES = ("mentor", "planner", "evaluator", "current_affairs", "rag")


class RouteDecision(BaseModel):
    """Structured supervisor decision."""

    route: Literal["mentor", "planner", "evaluator", "current_affairs", "rag"] = Field(
        ...,
        description=(
            "mentor = doubts/advice/chat; planner = build a study plan; "
            "evaluator = grade a written answer; current_affairs = news/editorials/"
            "monthly digest; rag = question about a specific document/chapter/lecture."
        ),
    )


_SUP_SYS = (
    "You are the router for a UPSC preparation assistant. Read the student's "
    "message and choose exactly one specialist:\n"
    "- mentor: general doubts, concept explanations, study advice, motivation, casual chat.\n"
    "- planner: requests to create or revise a study plan / timetable / schedule.\n"
    "- evaluator: requests to check, grade, or evaluate a written answer.\n"
    "- current_affairs: requests for daily/monthly current affairs, news, or editorials.\n"
    "- rag: questions about a specific uploaded document, NCERT chapter, lecture, or PYQ set.\n"
    "Default to mentor when unsure."
)


def _structured_llm(schema):
    """Structured-output runnable that tolerates fallback wrappers."""
    base = get_fast_llm()
    if hasattr(base, "with_structured_output"):
        return base.with_structured_output(schema)
    primary = base.runnable.with_structured_output(schema)
    fallbacks = [r.with_structured_output(schema) for r in base.fallbacks]
    return primary.with_fallbacks(fallbacks)


def build_supervisor(checkpointer=None, store=None):
    """Build and compile the top-level supervisor graph.

    Args:
        checkpointer: Short-term per-thread memory (see ``graph.memory``).
        store: Long-term cross-thread memory (see ``graph.memory``).
    """
    # Nested subgraphs share the parent state; they must NOT carry their own
    # checkpointer when nested under a checkpointed parent.
    mentor = build_mentor_graph()
    rag = build_rag_subgraph(label="rag")
    planner = build_planner_subgraph()
    evaluator = build_evaluator_subgraph()
    current_affairs = build_current_affairs_subgraph()

    def supervisor_node(state: AgentState) -> dict:
        # Respect an explicitly forced route (e.g. from the UI).
        forced = state.get("route")
        if forced in _ROUTES:
            return {"route": forced}
        try:
            decision = _structured_llm(RouteDecision).invoke(
                [("system", _SUP_SYS), ("human", state.get("question", ""))]
            )
            return {"route": decision.route}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Supervisor routing failed (%s); defaulting to mentor", exc)
            return {"route": "mentor"}

    def route_selector(
        state: AgentState,
    ) -> Literal["mentor", "planner", "evaluator", "current_affairs", "rag"]:
        route = state.get("route", "mentor")
        return route if route in _ROUTES else "mentor"

    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("mentor", mentor)
    graph.add_node("rag", rag)
    graph.add_node("planner", planner)
    graph.add_node("evaluator", evaluator)
    graph.add_node("current_affairs", current_affairs)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_selector,
        {name: name for name in _ROUTES},
    )
    for name in _ROUTES:
        graph.add_edge(name, END)
    return graph.compile(checkpointer=checkpointer, store=store)


# ============================ Local smoke test =================================
if __name__ == "__main__":
    app = build_supervisor(checkpointer=InMemorySaver())

    samples = [
        "Bhai polity me fundamental rights samjhao",            # -> mentor
        "Mera 2027 ka plan bana do, 8 ghante padh sakta hu",   # -> planner
        "Meri answer check karo aur marks do",                 # -> evaluator
        "Aaj ke current affairs do",                           # -> current_affairs
    ]

    # Routing-only preview (cheap: just the classifier, no heavy execution).
    print("=== ROUTING PREVIEW ===")
    router = _structured_llm(RouteDecision)
    for q in samples:
        decision = router.invoke([("system", _SUP_SYS), ("human", q)])
        print(f"{decision.route:16s} <- {q}")

    # One full end-to-end run through the mentor path.
    print("\n=== END-TO-END (mentor) ===")
    config = {"configurable": {"thread_id": "sup-test-1"}}
    result = app.invoke({"question": samples[0]}, config)
    print("route:", result.get("route"))
    print("answer:\n", result.get("answer"))
