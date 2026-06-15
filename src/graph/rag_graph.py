"""Reusable RAG subgraph factory with CRAG self-correction.

One factory powers every retrieval agent (NCERT, Lecture, Upload, PYQ). Each
caller pre-computes a Chroma ``persist_key`` (using the same
``make_persist_key`` helper the legacy agents already use) and places it on the
state; the subgraph then loads that collection and answers from it.

Graph flow (Corrective RAG / CRAG)::

    START -> retrieve -> grade -> (web_search?) -> generate -> END

Nodes:
    retrieve   Load the Chroma collection for ``state['persist_key']`` and run
               a relevance-scored search via ``similarity_search_with_sources``
               (re-using the existing 0.3 threshold + ``grounded`` flag).
    grade      Structured-output LLM judges whether the retrieved context can
               actually answer the question (the corrective step that catches
               weak/irrelevant retrievals before they reach generation).
    web_search Optional fallback to live web context when retrieval is not
               relevant, re-using the mentor module's search helper.
    generate   Produce a grounded answer, instructed to never fabricate facts.

The default prompt is a generic grounded-RAG template. To preserve an agent's
bespoke prompt (e.g. NCERT's subject/paper framing), pass that agent's
``ChatPromptTemplate`` as ``generate_prompt`` together with an ``input_builder``
that maps the state into that prompt's input variables.
"""
from __future__ import annotations

import os
import logging
from typing import Callable, Literal, Optional

from langchain_chroma import Chroma
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.core.llm import get_llm, get_fast_llm
from src.core.vector_store import (
    get_embeddings,
    persist_dir_for,
    similarity_search_with_sources,
)

# Re-use the mentor module's web search helper for the CRAG fallback.
from src.agents.mentor.graph import _fetch_search_context

logger = logging.getLogger(__name__)


# ============================ Default grounded prompt ==========================
GENERIC_RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a precise UPSC study assistant. Answer ONLY using the "
            "provided context and web results. If neither contains the answer, "
            "clearly say you do not have enough grounded information and advise "
            "verifying with a standard source. Never invent facts, dates, names, "
            "or article numbers.",
        ),
        (
            "human",
            "Question:\n{question}\n\n"
            "Retrieved context:\n{context}\n\n"
            "Web results (may be empty):\n{web_context}\n\n"
            "Write a clear, syllabus-focused answer with key points.",
        ),
    ]
)


def _default_input_builder(state: AgentState) -> dict:
    """Map graph state into the variables expected by ``GENERIC_RAG_PROMPT``."""
    return {
        "question": state.get("question", ""),
        "context": state.get("kb_context") or "No grounded context found.",
        "web_context": state.get("search_results") or "No web results available.",
    }


# ============================ Structured grader ================================
class RelevanceGrade(BaseModel):
    """CRAG grade: can the retrieved context answer the question?"""

    relevant: bool = Field(
        ...,
        description=(
            "True only if the retrieved context contains enough information to "
            "directly answer the question. False if it is empty, off-topic, or "
            "insufficient."
        ),
    )


_GRADE_SYS = (
    "You are a strict retrieval grader for a UPSC assistant. Decide whether the "
    "retrieved context is sufficient and on-topic to answer the question. Be "
    "conservative: if the context is empty or only loosely related, mark it not "
    "relevant so the system can fall back to a web search."
)


def _structured_llm(schema):
    """Return a structured-output runnable that tolerates fallback wrappers.

    ``get_fast_llm()`` may return either a raw chat model or a
    ``RunnableWithFallbacks`` (which does not expose ``with_structured_output``).
    In the latter case, structured output is applied to the primary runnable and
    each fallback individually.
    """
    base = get_fast_llm()
    if hasattr(base, "with_structured_output"):
        return base.with_structured_output(schema)
    primary = base.runnable.with_structured_output(schema)
    fallbacks = [r.with_structured_output(schema) for r in base.fallbacks]
    return primary.with_fallbacks(fallbacks)


# ============================ Factory ==========================================
def build_rag_subgraph(
    *,
    label: str = "rag",
    generate_prompt: ChatPromptTemplate = GENERIC_RAG_PROMPT,
    input_builder: Callable[[AgentState], dict] = _default_input_builder,
    k: int = 5,
    allow_web_fallback: bool = True,
    checkpointer=None,
):
    """Build and compile a reusable Corrective-RAG subgraph.

    Args:
        label: Short tag used for retrieval observability metrics.
        generate_prompt: Prompt used for answer generation. Defaults to a
            generic grounded-RAG template.
        input_builder: Maps the graph state into ``generate_prompt``'s input
            variables. Override this when supplying an agent-specific prompt.
        k: Number of chunks to retrieve.
        allow_web_fallback: When True, irrelevant retrievals fall back to a live
            web search before generation.
        checkpointer: Optional LangGraph checkpointer for conversation memory.
    """

    def retrieve_node(state: AgentState) -> dict:
        """Load the active Chroma collection and run a relevance-scored search."""
        persist_key = state.get("persist_key")
        if not persist_key:
            logger.info("[%s] no persist_key on state; skipping retrieval", label)
            return {"kb_context": "", "grounded": False, "citations": []}

        persist_dir = persist_dir_for(persist_key)
        if not os.path.exists(persist_dir):
            logger.info("[%s] collection not found: %s", label, persist_dir)
            return {"kb_context": "", "grounded": False, "citations": []}

        db = Chroma(persist_directory=persist_dir, embedding_function=get_embeddings())
        result = similarity_search_with_sources(db, state["question"], k=k, label=label)
        citations = [
            f"chunk (score={c['score']})"
            for c in result.get("chunks", [])
            if c.get("score") is not None
        ]
        return {
            "kb_context": result.get("context", ""),
            "grounded": result.get("grounded", False),
            "citations": citations,
        }

    def grade_node(state: AgentState) -> dict:
        """CRAG corrective step: judge whether context answers the question."""
        context = state.get("kb_context", "")
        if not context.strip():
            return {"rag_relevant": False}
        try:
            grader = _structured_llm(RelevanceGrade)
            grade = grader.invoke(
                [
                    ("system", _GRADE_SYS),
                    (
                        "human",
                        f"Question:\n{state['question']}\n\n"
                        f"Retrieved context:\n{context[:4000]}",
                    ),
                ]
            )
            return {"rag_relevant": bool(grade.relevant)}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[%s] grade failed (%s); assuming relevant", label, exc)
            return {"rag_relevant": True}

    def route_after_grade(state: AgentState) -> Literal["web_search", "generate"]:
        """Fall back to web search only when context is not relevant."""
        if state.get("rag_relevant"):
            return "generate"
        if allow_web_fallback:
            return "web_search"
        return "generate"

    def web_search_node(state: AgentState) -> dict:
        """Fetch live web context as a corrective fallback."""
        return {"search_results": _fetch_search_context(state["question"]) or ""}

    def generate_node(state: AgentState) -> dict:
        """Generate a grounded answer from context (and any web fallback)."""
        chain = generate_prompt | get_llm()
        resp = chain.invoke(input_builder(state))
        answer = resp.content if hasattr(resp, "content") else str(resp)
        return {"answer": answer, "messages": [AIMessage(content=answer)]}

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {"web_search": "web_search", "generate": "generate"},
    )
    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)


# ============================ Local smoke test =================================
if __name__ == "__main__":
    from src.core.config import settings

    rag_graph = build_rag_subgraph(label="ncert", checkpointer=InMemorySaver())

    # Try to find an existing NCERT collection so we can test grounded retrieval.
    base = settings.chroma_persist_dir
    existing = (
        [d for d in os.listdir(base) if d.startswith("ncert")]
        if os.path.exists(base)
        else []
    )
    persist_key = existing[0] if existing else ""
    print("Using persist_key:", persist_key or "(none - will test web fallback path)")

    config = {"configurable": {"thread_id": "rag-test-1"}}
    result = rag_graph.invoke(
        {
            "question": "Explain the main idea of this chapter.",
            "persist_key": persist_key,
        },
        config,
    )
    print("\n" + "=" * 60)
    print(
        "grounded:", result.get("grounded"),
        "| relevant:", result.get("rag_relevant"),
        "| citations:", result.get("citations"),
    )
    print("ANSWER:\n", result.get("answer"))
