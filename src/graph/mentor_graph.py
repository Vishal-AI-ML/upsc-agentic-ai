"""Mentor subgraph - LangGraph port of ``src/agents/mentor/graph.py``.

Graph flow::

    START -> router -> retrieve_kb -> (web_search?) -> generate -> END

Nodes:
    router       Structured-output LLM intent classifier (replaces the legacy
                 regex-based ``detect_intent``).
    retrieve_kb  Grounded knowledge-base lookup via ``mentor_kb.search_kb``;
                 only runs for the "academic" intent.
    web_search   Live web context via ``_fetch_search_context``; only runs for
                 academic questions that require current/volatile facts.
    generate     Builds the final answer using the intent-appropriate
                 ``ChatPromptTemplate`` piped into ``get_llm()``.

All prompts and helper functions are reused from the existing mentor module;
only the routing layer was migrated from regex to a structured LLM decision.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.core.llm import get_llm, get_fast_llm
from src.core import mentor_kb

# Reuse existing mentor helpers (web search, news cache, context formatters).
from src.agents.mentor.graph import (
    _fetch_search_context,
    _fetch_latest_upsc_news,
    _build_student_context,
    _format_chat_history,
)
from src.agents.mentor.prompts import (
    CASUAL_PROMPT,
    VAGUE_PROMPT,
    EMOTIONAL_PROMPT,
    MENTOR_PROMPT,
)


# ============================ 1. Router (structured) ===========================
class IntentDecision(BaseModel):
    """Structured classification of a student message."""

    intent: Literal["casual", "vague", "emotional", "academic"] = Field(
        ...,
        description=(
            "casual = greeting/chit-chat; vague = unclear request; "
            "emotional = stress/motivation; academic = concrete UPSC question"
        ),
    )
    needs_web_search: bool = Field(
        ...,
        description=(
            "True only when current/volatile information is required "
            "(exam dates, notifications, results, cut-offs, vacancies, recent news)."
        ),
    )


_ROUTER_SYS = (
    "You route messages for a UPSC mentor named Arjun. Classify the student's "
    "message into exactly one intent and decide whether a live web search is "
    "needed. Treat capability/meta questions (e.g. 'what can you do', 'how can "
    "you help me') and simple factual questions (e.g. today's date) as 'casual'. "
    "Use 'vague' only when an academic request is genuinely unclear. "
    "Set needs_web_search to True ONLY for volatile/current facts "
    "(exam dates, notifications, results, cut-offs, vacancies, recent news)."
)


def _router_llm():
    """Return a structured-output router runnable.

    Works whether ``get_fast_llm()`` returns a raw chat model or a
    ``RunnableWithFallbacks`` wrapper. Wrappers do not expose
    ``with_structured_output`` directly, so in that case structured output is
    re-applied to the primary runnable and each fallback individually.
    """
    base = get_fast_llm()
    if hasattr(base, "with_structured_output"):
        return base.with_structured_output(IntentDecision)
    primary = base.runnable.with_structured_output(IntentDecision)
    fallbacks = [r.with_structured_output(IntentDecision) for r in base.fallbacks]
    return primary.with_fallbacks(fallbacks)


def router_node(state: AgentState) -> dict:
    """Classify the incoming question and decide if web search is needed."""
    decision = _router_llm().invoke(
        [("system", _ROUTER_SYS), ("human", state["question"])]
    )
    return {
        "intent": decision.intent,
        "needs_web_search": decision.needs_web_search,
    }


# ============================ 2. Knowledge-base retrieval ======================
def retrieve_kb_node(state: AgentState) -> dict:
    """Look up grounded background knowledge for academic questions only."""
    if state.get("intent") != "academic":
        return {"kb_context": "", "citations": [], "grounded": False}

    kb = mentor_kb.search_kb(state["question"], k=4)
    return {
        "kb_context": kb.get("context", ""),
        "citations": kb.get("citations", []),
        "grounded": kb.get("grounded", False),
    }


def route_after_retrieve(state: AgentState) -> Literal["web_search", "generate"]:
    """Branch to web search only for academic questions needing live facts."""
    if state.get("intent") == "academic" and state.get("needs_web_search"):
        return "web_search"
    return "generate"


# ============================ 3. Web search ====================================
def web_search_node(state: AgentState) -> dict:
    """Fetch live web context for current/volatile facts."""
    return {"search_results": _fetch_search_context(state["question"]) or ""}


# ============================ 4. Answer generation =============================
def generate_node(state: AgentState) -> dict:
    """Generate the final answer using the intent-appropriate prompt."""
    intent = state.get("intent", "academic")
    question = state["question"]
    current_date = datetime.now().strftime("%B %d, %Y")
    llm = get_llm()

    if intent == "casual":
        chain = CASUAL_PROMPT | llm
        resp = chain.invoke(
            {
                "question": question,
                "latest_news": _fetch_latest_upsc_news()
                or "No major updates right now.",
                "current_date": current_date,
            }
        )
    elif intent == "vague":
        chain = VAGUE_PROMPT | llm
        resp = chain.invoke({"question": question, "current_date": current_date})
    elif intent == "emotional":
        chain = EMOTIONAL_PROMPT | llm
        resp = chain.invoke({"question": question, "current_date": current_date})
    else:  # academic
        chain = MENTOR_PROMPT | llm
        resp = chain.invoke(
            {
                "question": question,
                "current_date": current_date,
                "student_context": _build_student_context(state.get("student_context")),
                "chat_history": _format_chat_history(state.get("chat_history")),
                "kb_context": state.get("kb_context")
                or "No matching background knowledge.",
                "search_results": state.get("search_results")
                or "No live search data - for exact dates/cut-offs/vacancies, verify at upsc.gov.in.",
            }
        )

    answer = resp.content if hasattr(resp, "content") else str(resp)
    return {"answer": answer, "messages": [AIMessage(content=answer)]}


# ============================ Graph builder ====================================
def build_mentor_graph(checkpointer=None):
    """Compile and return the mentor subgraph.

    Args:
        checkpointer: Optional LangGraph checkpointer for conversation memory.
            Use ``InMemorySaver`` for local testing; a Postgres-backed saver
            in production.
    """
    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("retrieve_kb", retrieve_kb_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "retrieve_kb")
    graph.add_conditional_edges(
        "retrieve_kb",
        route_after_retrieve,
        {"web_search": "web_search", "generate": "generate"},
    )
    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)


# ============================ Local smoke test =================================
if __name__ == "__main__":
    mentor_graph = build_mentor_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "mentor-test-1"}}

    sample_questions = [
        "Hello bhai",
        "Bhai polity me fundamental rights kaise yaad karu?",
        "Yaar main thak gaya hu, kuch nahi ho raha",
    ]
    for question in sample_questions:
        result = mentor_graph.invoke({"question": question}, config)
        print("\n" + "=" * 60)
        print("Q:", question)
        print(
            "INTENT:", result.get("intent"),
            "| web:", result.get("needs_web_search"),
            "| grounded:", result.get("grounded"),
        )
        print("ANSWER:\n", result.get("answer"))
