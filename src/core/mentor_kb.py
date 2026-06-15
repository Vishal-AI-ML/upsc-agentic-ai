"""
Mentor Knowledge Base - grounded, citeable knowledge for the Mentor agent.

One persistent Chroma store ("mentor_kb") holding DURABLE, slow-changing knowledge:
  - Verified UPSC facts (exam pattern, eligibility, syllabus) from a curated, DATED
    markdown file.
  - Topper strategies from YouTube interview transcripts (attributed to topper + year).
  - Optional official PDFs (notification / syllabus).

VOLATILE facts (exact dates, cutoffs, vacancy numbers) are deliberately NOT stored
here - the Mentor agent fetches those live from official sources. This KB only holds
knowledge that stays valid for a long time, and every chunk carries a 'source' label
so the Mentor can cite it to the user.

Rebuild whenever the facts file changes or topper videos are added:
    python scripts/ingest_mentor_kb.py
"""
import os
import shutil
import logging
from typing import Optional

from langchain_chroma import Chroma

from src.core.vector_store import (
    get_embeddings,
    get_text_splitter,
    persist_dir_for,
    make_persist_key,
)

logger = logging.getLogger(__name__)

KB_KEY = make_persist_key("mentor", "kb")
# Separate, tunable threshold for the mentor KB (general knowledge needs a slightly
# looser bar than tight chapter RAG).
KB_THRESHOLD = float(os.getenv("MENTOR_KB_THRESHOLD", "0.25"))


def kb_dir() -> str:
    """Canonical on-disk Chroma dir for the mentor KB."""
    return persist_dir_for(KB_KEY)


def kb_exists() -> bool:
    d = kb_dir()
    return os.path.isdir(d) and bool(os.listdir(d))


def _make_docs(sources):
    """sources: list of {"text": str, "metadata": dict}. Returns split LC documents."""
    splitter = get_text_splitter()
    docs = []
    for s in sources:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        md = dict(s.get("metadata") or {})
        # Chroma metadata values must be str/int/float/bool (no None).
        md = {k: v for k, v in md.items() if v is not None}
        docs.extend(splitter.create_documents([text], metadatas=[md]))
    return docs


def build_kb(sources, rebuild: bool = True) -> int:
    """
    Build (or rebuild) the Mentor KB from a list of sources.
    Each source: {"text": <str>, "metadata": {"source": <citation label>, ...}}.
    Returns the number of chunks indexed.
    """
    docs = _make_docs(sources)
    if not docs:
        logger.warning("Mentor KB: no documents to index (nothing ingested)")
        return 0
    d = kb_dir()
    if rebuild and os.path.isdir(d):
        logger.info(f"Mentor KB: clearing existing store at {d}")
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    Chroma.from_documents(docs, get_embeddings(), persist_directory=d)
    logger.info(f"Mentor KB built: {len(docs)} chunks -> {d}")
    return len(docs)


def search_kb(query: str, k: int = 4, min_score: Optional[float] = None) -> dict:
    """
    Search the Mentor KB.

    Returns:
        {"context": str, "citations": [str], "grounded": bool}
    where each context block is prefixed with its source label, and 'citations'
    is the de-duplicated list of source labels for user-facing attribution.
    """
    q = (query or "").strip()
    if not q or not kb_exists():
        return {"context": "", "citations": [], "grounded": False}
    threshold = KB_THRESHOLD if min_score is None else min_score
    try:
        db = Chroma(persist_directory=kb_dir(), embedding_function=get_embeddings())
        scored = db.similarity_search_with_relevance_scores(q, k=k)
    except Exception as e:
        logger.warning(f"Mentor KB search failed: {e}")
        return {"context": "", "citations": [], "grounded": False}

    parts, citations = [], []
    for doc, score in scored:
        if score is None or score >= threshold:
            src = (doc.metadata or {}).get("source")
            prefix = f"[{src}] " if src else ""
            parts.append(f"{prefix}{doc.page_content}")
            if src and src not in citations:
                citations.append(src)

    try:
        from src.core import observability
        observability.log_retrieval_metrics("mentor_kb", q, k, len(parts), [s for _, s in scored])
    except Exception:
        pass

    return {
        "context": "\n\n".join(parts),
        "citations": citations,
        "grounded": bool(parts),
    }
