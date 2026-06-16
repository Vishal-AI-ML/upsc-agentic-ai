"""
Vector store utilities.

Backend is chosen at runtime:
  - Qdrant (managed / self-hosted) when settings.qdrant_url is set  -> production.
  - Local Chroma (on-disk) otherwise                               -> local dev fallback.

The public API (create_vector_store, load_vector_store, similarity_search,
similarity_search_with_sources, make_persist_key, ...) is backend-agnostic, so
callers do not need to know which store is active. Each persist_key maps to one
Qdrant collection (or one on-disk Chroma directory in the fallback path).
"""

import os
import shutil
import logging
from typing import Any, Optional

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import settings

logger = logging.getLogger(__name__)

_embeddings_instance = None
_qdrant_client_instance = None

# Minimum relevance score (0..1, higher = more similar) for a chunk to count
# as grounded context. Tune via env without code changes.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))


# --------------------------------------------------------------------------- #
# Embeddings + text splitting (backend-agnostic)
# --------------------------------------------------------------------------- #
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
        separators=["\n\n", "\n", "\u0964", ".", " "],
    )


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


def _safe_persist_key(persist_key: str) -> str:
    """Sanitize a persist key into a filesystem-/collection-safe name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in persist_key)


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
def _use_qdrant() -> bool:
    """True when a Qdrant endpoint is configured; else use local Chroma."""
    return bool(settings.qdrant_url)


def collection_for(persist_key: str) -> str:
    """Qdrant collection name for a persist key (single source of truth)."""
    return _safe_persist_key(persist_key)


def persist_dir_for(persist_key: str) -> str:
    """Canonical on-disk Chroma dir for a persist key (Chroma fallback only)."""
    return os.path.join(settings.chroma_persist_dir, _safe_persist_key(persist_key))


def get_qdrant_client():
    """Get a cached Qdrant client (cloud or self-hosted)."""
    global _qdrant_client_instance
    if _qdrant_client_instance is None:
        from qdrant_client import QdrantClient

        _qdrant_client_instance = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=settings.qdrant_timeout,
        )
        logger.info(f"Qdrant client connected: {settings.qdrant_url}")
    return _qdrant_client_instance


def _embedding_dim(embeddings) -> int:
    """Probe the embedding model's output dimensionality once."""
    return len(embeddings.embed_query("dimension probe"))


def _ensure_qdrant_collection(client, name: str, embeddings) -> None:
    """Create a cosine-distance collection sized to the embedding model if missing."""
    if client.collection_exists(name):
        return
    from qdrant_client.http.models import Distance, VectorParams

    dim = _embedding_dim(embeddings)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    logger.info(f"Qdrant collection created: {name} (dim={dim}, cosine)")


def _qdrant_has_points(client, name: str) -> bool:
    """True if the collection exists and holds at least one vector."""
    try:
        if not client.collection_exists(name):
            return False
        return client.count(collection_name=name, exact=False).count > 0
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Qdrant count check failed for '{name}': {e}")
        return False


# --------------------------------------------------------------------------- #
# Storage readiness (called once on app startup)
# --------------------------------------------------------------------------- #
def ensure_vector_storage() -> bool:
    """
    Verify the active vector backend on startup and report durability.

    Qdrant  -> ping the server; returns True (managed store survives restarts).
    Chroma  -> create the persist dir; returns True only for an absolute path
               (a relative/default path is EPHEMERAL on most cloud hosts).
    """
    if _use_qdrant():
        try:
            get_qdrant_client().get_collections()
            logger.info(
                f"Vector store backend: Qdrant (durable, managed) -> {settings.qdrant_url}"
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"Qdrant configured but unreachable ({e}). "
                "Check QDRANT_URL / QDRANT_API_KEY. Vector ops will fail until fixed."
            )
            return False

    persist_dir = settings.chroma_persist_dir
    os.makedirs(persist_dir, exist_ok=True)
    durable = os.path.isabs(persist_dir)
    if durable:
        logger.info(f"Vector store backend: Chroma (durable): {persist_dir}")
    else:
        logger.warning(
            f"Vector store backend: Chroma dir '{persist_dir}' is relative -> likely "
            "EPHEMERAL on cloud hosts. Set QDRANT_URL (recommended) or point "
            "CHROMA_PERSIST_DIR at a mounted persistent disk."
        )
    return durable


# --------------------------------------------------------------------------- #
# Existence / loading
# --------------------------------------------------------------------------- #
def vector_store_exists(persist_key: str) -> bool:
    """True if a populated store already exists for this persist key."""
    if not persist_key:
        return False
    if _use_qdrant():
        return _qdrant_has_points(get_qdrant_client(), collection_for(persist_key))
    d = persist_dir_for(persist_key)
    return os.path.isdir(d) and bool(os.listdir(d))


def load_vector_store(persist_key: str) -> Optional[Any]:
    """
    Load an existing vector store for a persist key, or None if it does not exist.

    Use this for read/search paths instead of constructing a backend store
    directly, so the active backend (Qdrant vs Chroma) stays transparent.
    """
    if not persist_key:
        return None
    embeddings = get_embeddings()
    if _use_qdrant():
        from langchain_qdrant import QdrantVectorStore

        client = get_qdrant_client()
        name = collection_for(persist_key)
        if not client.collection_exists(name):
            return None
        return QdrantVectorStore(
            client=client, collection_name=name, embedding=embeddings
        )

    from langchain_chroma import Chroma

    d = persist_dir_for(persist_key)
    if not (os.path.isdir(d) and os.listdir(d)):
        return None
    return Chroma(persist_directory=d, embedding_function=embeddings)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def upsert_documents(persist_key: str, docs, rebuild: bool = False) -> Optional[Any]:
    """
    Index pre-built LangChain documents (text + metadata) for a persist key.

    rebuild=True drops any existing data for the key first (full refresh).
    Returns the populated vector store, or None when there is nothing to index.
    """
    if not docs:
        logger.warning(f"upsert_documents: no documents for key '{persist_key}'")
        return None
    embeddings = get_embeddings()

    if _use_qdrant():
        from langchain_qdrant import QdrantVectorStore

        client = get_qdrant_client()
        name = collection_for(persist_key)
        if rebuild and client.collection_exists(name):
            client.delete_collection(name)
            logger.info(f"Qdrant collection dropped for rebuild: {name}")
        _ensure_qdrant_collection(client, name, embeddings)
        store = QdrantVectorStore(
            client=client, collection_name=name, embedding=embeddings
        )
        store.add_documents(docs)
        logger.info(f"Qdrant indexed {len(docs)} chunks -> collection '{name}'")
        return store

    from langchain_chroma import Chroma

    d = persist_dir_for(persist_key)
    if rebuild and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    store = Chroma.from_documents(docs, embeddings, persist_directory=d)
    logger.info(f"Chroma indexed {len(docs)} chunks -> {d}")
    return store


def create_vector_store(text: str, persist_key: str = "") -> Any:
    """
    Create or load a vector store from raw text.

    Args:
        text: Document text to embed.
        persist_key: Unique key for persistence (e.g. 'ncert_class6_history_ch1').
                     If empty, an ephemeral in-memory store is returned.

    Behaviour matches the old Chroma version: if a populated store already
    exists for the key, it is loaded and returned as-is (no duplicate indexing).
    """
    embeddings = get_embeddings()

    # Ephemeral, no-persistence path (kept on local Chroma; rarely used).
    if not persist_key:
        from langchain_chroma import Chroma

        logger.info("Creating in-memory vector store")
        docs = get_text_splitter().create_documents([text])
        return Chroma.from_documents(docs, embeddings)

    # Idempotent: reuse an already-populated store instead of re-indexing.
    if vector_store_exists(persist_key):
        logger.info(f"Loading existing vector store for key '{persist_key}'")
        existing = load_vector_store(persist_key)
        if existing is not None:
            return existing

    docs = get_text_splitter().create_documents([text])
    return upsert_documents(persist_key, docs, rebuild=False)


# --------------------------------------------------------------------------- #
# Searching (works on any LangChain vector store: Qdrant or Chroma)
# --------------------------------------------------------------------------- #
def similarity_search(
    db: Any, query: str, k: int = 5, min_score: Optional[float] = None, label: str = "rag"
) -> str:
    """
    Relevance-scored similarity search returning joined context.

    Only chunks scoring >= the relevance threshold are returned, so a caller's
    `if not context:` guard actually triggers when nothing relevant is found.
    This prevents irrelevant chunks leaking into answers (hallucination risk).

    Args:
        db: A loaded vector store (from load_vector_store / create_vector_store).
        query: Search query.
        k: Max number of results to consider.
        min_score: Override the default relevance threshold (0..1).

    Returns:
        Joined context from relevant results, or "" if none clear the bar.
    """
    if db is None:
        return ""
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
    db: Any, query: str, k: int = 5, min_score: Optional[float] = None, label: str = "rag"
) -> dict:
    """
    Like similarity_search but also returns per-chunk relevance scores so routes
    can surface lightweight source citations / a grounding indicator.

    Returns:
        {"context": str, "chunks": [{"excerpt": str, "score": float|None}], "grounded": bool}
    """
    if db is None:
        return {"context": "", "chunks": [], "grounded": False}
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
