"""Form-style agent subgraphs: Planner, Evaluator, Current Affairs.

Unlike the mentor and RAG agents (free-text question in, answer out), these
three are driven by structured form inputs in the original app. To fit them
into the shared graph contract without rewriting their business logic, each
subgraph reads its parameters from ``state['task_inputs']`` and wraps the
existing streaming functions, collecting the streamed chunks into a single
answer string.

Expected ``task_inputs`` shapes:
    planner          {goal, hours, optional, weak, attempt_number}
    evaluator        {question, answer, marks?, keywords?, word_limit?}
                     (marks present -> Mains rubric; otherwise basic evaluation)
    current_affairs  {mode: "daily"|"editorial"|"monthly", date|topic|month+year}
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

from src.graph.state import AgentState
from src.agents.planner.graph import generate_plan
from src.agents.evaluator.graph import evaluate_answer, evaluate_mains
from src.agents.current_affairs.graph import (
    get_daily_ca,
    get_editorial,
    get_monthly_summary,
)

logger = logging.getLogger(__name__)


def _consume(generator) -> str:
    """Collect a streaming generator of text chunks into a single string."""
    parts = [chunk for chunk in generator if isinstance(chunk, str)]
    return "".join(parts)


# ============================ Planner =========================================
def build_planner_subgraph(checkpointer=None):
    """Subgraph wrapping the study-plan generator."""

    def planner_node(state: AgentState) -> dict:
        params = state.get("task_inputs") or {}
        text = _consume(
            generate_plan(
                goal=params.get("goal", state.get("question", "")),
                hours=str(params.get("hours", "6")),
                optional=params.get("optional", ""),
                weak=params.get("weak", ""),
                attempt_number=str(params.get("attempt_number", "1")),
            )
        )
        return {"answer": text, "messages": [AIMessage(content=text)]}

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", END)
    return graph.compile(checkpointer=checkpointer)


# ============================ Evaluator =======================================
def build_evaluator_subgraph(checkpointer=None):
    """Subgraph wrapping answer evaluation (basic + Mains rubric)."""

    def evaluator_node(state: AgentState) -> dict:
        params = state.get("task_inputs") or {}
        question = params.get("question", state.get("question", ""))
        answer = params.get("answer", "")
        if params.get("marks"):
            generator = evaluate_mains(
                question=question,
                answer=answer,
                marks=int(params.get("marks", 10)),
                keywords=params.get("keywords"),
                word_limit=int(params.get("word_limit", 150)),
            )
        else:
            generator = evaluate_answer(question=question, answer=answer)
        text = _consume(generator)
        return {"answer": text, "messages": [AIMessage(content=text)]}

    graph = StateGraph(AgentState)
    graph.add_node("evaluator", evaluator_node)
    graph.add_edge(START, "evaluator")
    graph.add_edge("evaluator", END)
    return graph.compile(checkpointer=checkpointer)


# ============================ Current Affairs =================================
def build_current_affairs_subgraph(checkpointer=None):
    """Subgraph wrapping daily CA, editorials, and the monthly digest."""

    def current_affairs_node(state: AgentState) -> dict:
        params = state.get("task_inputs") or {}
        mode = (params.get("mode") or "daily").lower()
        if mode == "editorial":
            generator = get_editorial(params.get("topic", ""))
        elif mode == "monthly":
            generator = get_monthly_summary(
                params.get("month", ""), params.get("year", "")
            )
        else:
            generator = get_daily_ca(params.get("date", ""))
        text = _consume(generator)
        return {"answer": text, "messages": [AIMessage(content=text)]}

    graph = StateGraph(AgentState)
    graph.add_node("current_affairs", current_affairs_node)
    graph.add_edge(START, "current_affairs")
    graph.add_edge("current_affairs", END)
    return graph.compile(checkpointer=checkpointer)
