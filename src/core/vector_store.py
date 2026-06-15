"""
Vector store utilities - ChromaDB with persistence
"""

import os
import logging
from typing import Optional
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.config import settings

logger = logging.getLogger(__name__)

_embeddings_instance = None

# Minimum relevance score (0..1, higher = more similar) for a chunk to count
# as grounded context. Tune via env without code changes.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Get cached embeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key,
        )
        logger.info(f"Embeddings initialized: {settings.embedding_model}")
    return _embeddings_instance


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Get text splitter with configured chunk size."""
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", "।", ".", " "],
    )


def _safe_persist_key(persist_key: str) -> str:
    """Sanitize a persist key into a filesystem-safe folder name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in persist_key)


def persist_dir_for(persist_key: str) -> str:
    """Canonical on-disk Chroma dir for a persist key (single source of truth)."""
    return os.path.join(settings.chroma_persist_dir, _safe_persist_key(persist_key))


def ensure_vector_storage() -> bool:
    """
    Create the Chroma persistence dir on startup and report durability.

    Returns True if CHROMA_PERSIST_DIR is an absolute path (typically a mounted
    persistent disk => survives restarts). Returns False for a relative/default
    path, which is EPHEMERAL on most cloud hosts (vectors lost on restart).
    """
    persist_dir = settings.chroma_persist_dir
    os.makedirs(persist_dir, exist_ok=True)
    durable = os.path.isabs(persist_dir)
    if durable:
        logger.info(f"Vector store persistence ready (durable): {persist_dir}")
    else:
        logger.warning(
            f"Vector store dir '{persist_dir}' is relative -> likely EPHEMERAL on "
            "cloud hosts. Set CHROMA_PERSIST_DIR to a mounted persistent disk "
            "(e.g. /var/data/chroma_db) so embeddings survive restarts."
        )
    return durable


def create_vector_store(text: str, persist_key: str = "") -> Chroma:
    """
    Create or load a persistent Chroma vector store.
    
    Args:
        text: Document text to embed
        persist_key: Unique key for persistence (e.g. 'ncert_class6_history_ch1')
                     If empty, creates in-memory store (no persistence)
    
    Returns:
        Chroma vector store
    """
    embeddings = get_embeddings()
    
    # Persistent store
    if persist_key:
        persist_dir = persist_dir_for(persist_key)
        
        if os.path.exists(persist_dir):
            logger.info(f"Loading existing vector store: {persist_dir}")
            try:
                return Chroma(
                    persist_directory=persist_dir,
                    embedding_function=embeddings,
                )
            except Exception as e:
                logger.warning(f"Could not load existing store, recreating: {e}")
        
        logger.info(f"Creating new vector store: {persist_dir}")
        os.makedirs(persist_dir, exist_ok=True)
        docs = get_text_splitter().create_documents([text])
        db = Chroma.from_documents(
            docs,
            embeddings,
            persist_directory=persist_dir,
        )
        logger.info(f"Vector store created: {len(docs)} chunks -> {persist_dir}")
        return db
    
    # In-memory store (no persistence)
    logger.info("Creating in-memory vector store")
    docs = get_text_splitter().create_documents([text])
    return Chroma.from_documents(docs, embeddings)


def similarity_search(
    db: Chroma, query: str, k: int = 5, min_score: Optional[float] = None, label: str = "rag"
) -> str:
    """
    Relevance-scored similarity search returning joined context.

    Only chunks scoring >= the relevance threshold are returned, so a caller's
    `if not context:` guard actually triggers when nothing relevant is found.
    This prevents irrelevant chunks leaking into answers (hallucination risk).

    Args:
        db: Chroma vector store
        query: Search query
        k: Max number of results to consider
        min_score: Override the default relevance threshold (0..1)

    Returns:
        Joined context from relevant results, or "" if none clear the bar.
    """
    threshold = SIMILARITY_THRESHOLD if min_score is None else min_score
    q = (query or "").strip()
    if not q:
        return ""
    try:
        scored = db.similarity_search_with_relevance_scores(q, k=k)
        relevant = [doc for doc, score in scored if score is not None and score >= threshold]
        try:
            from src.core import observability
            observability.log_retrieval_metrics(label, q, k, len(relevant), [s for _, s in scored])
        except Exception:
            pass
        if not relevant:
            best = max([sc for _, sc in scored], default=0.0) or 0.0
            logger.info(
                f"No chunks cleared relevance threshold {threshold} (best={best:.3f})"
            )
            return ""
        return "\n\n".join(doc.page_content for doc in relevant)
    except Exception as e:
        logger.warning(f"Scored search failed ({e}); falling back to plain search")
        try:
            results = db.similarity_search(q, k=k)
            return "\n\n".join(r.page_content for r in results) if results else ""
        except Exception as e2:
            logger.error(f"Similarity search failed: {e2}")
            return ""


def similarity_search_with_sources(
    db: Chroma, query: str, k: int = 5, min_score: Optional[float] = None, label: str = "rag"
) -> dict:
    """
    Like similarity_search but also returns per-chunk relevance scores so routes
    can surface lightweight source citations / a grounding indicator.

    Returns:
        {"context": str, "chunks": [{"excerpt": str, "score": float|None}], "grounded": bool}
    """
    threshold = SIMILARITY_THRESHOLD if min_score is None else min_score
    q = (query or "").strip()
    if not q:
        return {"context": "", "chunks": [], "grounded": False}
    try:
        scored = db.similarity_search_with_relevance_scores(q, k=k)
    except Exception as e:
        logger.warning(f"Scored search failed ({e}); falling back to plain search")
        try:
            docs = db.similarity_search(q, k=k)
            scored = [(d, None) for d in docs]
        except Exception as e2:
            logger.error(f"Similarity search failed: {e2}")
            return {"context": "", "chunks": [], "grounded": False}
    chunks = []
    for doc, score in scored:
        if score is None or score >= threshold:
            chunks.append({
                "excerpt": doc.page_content,
                "score": round(score, 3) if score is not None else None,
            })
    context = "\n\n".join(c["excerpt"] for c in chunks)
    try:
        from src.core import observability
        observability.log_retrieval_metrics(label, q, k, len(chunks), [c["score"] for c in chunks])
    except Exception:
        pass
    return {"context": context, "chunks": chunks, "grounded": bool(chunks)}


def make_persist_key(*parts: str) -> str:
    """
    Helper to create clean persist keys.
    
    Usage:
        make_persist_key("ncert", "class6", "history", "chapter1")
        -> "ncert_class6_history_chapter1"
    """
    return "_".join(
        part.strip().lower().replace(" ", "_").replace("/", "_")
        for part in parts
        if part and part.strip()
    )
