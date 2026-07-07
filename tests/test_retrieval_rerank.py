"""Offline tests for lightweight hybrid retrieval ranking."""
from dataclasses import dataclass

from src.core.retrieval import lexical_overlap_score, hybrid_score, rerank_scored_documents


@dataclass
class Doc:
    page_content: str


def test_lexical_overlap_ignores_stopwords():
    score = lexical_overlap_score("What is curiosity in science?", "Science starts with curiosity and observation.")
    assert score > 0.5


def test_hybrid_score_combines_vector_and_lexical():
    assert hybrid_score(0.8, 0.4) == 0.7
    assert hybrid_score(None, 1.0) == 0.25


def test_rerank_prefers_semantic_score_then_lexical_support():
    rows = [
        (Doc("unrelated chunk about sports"), 0.82),
        (Doc("science curiosity observation discovery"), 0.8),
    ]
    ranked = rerank_scored_documents(rows, "science curiosity discovery")
    assert ranked[0]["doc"].page_content == "science curiosity observation discovery"
    assert ranked[0]["hybrid_score"] > ranked[1]["hybrid_score"]
