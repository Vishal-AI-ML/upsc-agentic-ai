"""Lightweight hybrid retrieval helpers.

No extra dependency: combines vector relevance score with lexical overlap so
retrieved chunks that share important query terms are ranked higher before
context packing.
"""
from __future__ import annotations

import re
from typing import Any

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "was", "were",
    "what", "why", "how", "does", "do", "did", "according", "chapter", "explain", "main", "idea",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{2,}")


def query_terms(text: str) -> set[str]:
    """Return normalized, non-trivial lexical query terms."""
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS}


def lexical_overlap_score(query: str, document: str) -> float:
    """Fraction of important query terms present in a document chunk."""
    terms = query_terms(query)
    if not terms:
        return 0.0
    doc_terms = query_terms(document)
    return round(len(terms & doc_terms) / len(terms), 3)


def hybrid_score(vector_score: float | None, lexical_score: float, *, vector_weight: float = 0.75) -> float:
    """Combine vector relevance and lexical overlap into one ranking score."""
    vector = 0.0 if vector_score is None else max(0.0, min(1.0, float(vector_score)))
    lexical = max(0.0, min(1.0, float(lexical_score)))
    weight = max(0.0, min(1.0, vector_weight))
    return round((weight * vector) + ((1.0 - weight) * lexical), 3)


def rerank_scored_documents(scored_docs: list[tuple[Any, float | None]], query: str) -> list[dict[str, Any]]:
    """Return docs sorted by hybrid score, preserving original vector score."""
    ranked = []
    for doc, score in scored_docs:
        excerpt = getattr(doc, "page_content", "") or ""
        lex = lexical_overlap_score(query, excerpt)
        ranked.append({
            "doc": doc,
            "score": round(score, 3) if score is not None else None,
            "lexical_score": lex,
            "hybrid_score": hybrid_score(score, lex),
        })
    ranked.sort(key=lambda row: (row["hybrid_score"], row["score"] or 0.0), reverse=True)
    return ranked
