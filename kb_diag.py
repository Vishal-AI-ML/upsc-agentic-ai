"""Mentor KB / Qdrant diagnostic. Run: uv run python kb_diag.py

Kuch bhi mutate nahi karta -- sirf padhta hai aur print karta hai.
Output poora copy karke bhej dena.
"""
import sys

print("=" * 60)
print("UPSC KB DIAGNOSTIC")
print("=" * 60)

# 1) Embedding dimension actually being produced
try:
    from src.core.vector_store import get_embeddings
    e = get_embeddings()
    dim = len(e.embed_query("dimension probe"))
    print(f"[1] Embedding wrapper type : {type(e).__name__}")
    print(f"[1] Live embedding dim     : {dim}")
except Exception as ex:
    print(f"[1] EMBEDDING ERROR: {ex}")
    sys.exit(1)

# 2) All Qdrant collections: name, points, vector size
try:
    from src.core.vector_store import get_qdrant_client
    client = get_qdrant_client()
    cols = client.get_collections().collections
    print(f"\n[2] Qdrant collections ({len(cols)}):")
    for c in cols:
        name = c.name
        try:
            info = client.get_collection(name)
            cnt = client.count(name, exact=True).count
            vecs = info.config.params.vectors
            # vectors can be a single VectorParams or a dict of named vectors
            if hasattr(vecs, "size"):
                size = vecs.size
            elif isinstance(vecs, dict):
                size = {k: getattr(v, "size", "?") for k, v in vecs.items()}
            else:
                size = "?"
            print(f"    - {name:35s} points={cnt:<7} dim={size}")
        except Exception as ie:
            print(f"    - {name:35s} (info error: {ie})")
except Exception as ex:
    print(f"[2] QDRANT ERROR: {ex}")

# 3) Mentor KB existence + which collection it maps to
try:
    from src.core import mentor_kb
    print(f"\n[3] Mentor KB key      : {mentor_kb.KB_KEY}")
    print(f"[3] Mentor KB location : {mentor_kb.kb_location()}")
    print(f"[3] Mentor KB exists   : {mentor_kb.kb_exists()}")
    print(f"[3] Mentor KB threshold: {mentor_kb.KB_THRESHOLD}")
except Exception as ex:
    print(f"[3] MENTOR KB ERROR: {ex}")

# 4) Raw scored search (bypasses threshold) so we SEE the scores
queries = [
    "Minerva Mills judgment basic structure doctrine",
    "DPSP Fundamental Rights conflict Supreme Court",
    "UPSC exam pattern syllabus",
]
try:
    from src.core.vector_store import load_vector_store
    from src.core import mentor_kb
    db = load_vector_store(mentor_kb.KB_KEY)
    if db is None:
        print("\n[4] load_vector_store(mentor_kb) -> None (collection missing/empty)")
    else:
        for q in queries:
            try:
                scored = db.similarity_search_with_relevance_scores(q, k=4)
                print(f"\n[4] Query: {q!r}  -> {len(scored)} hits")
                for i, (doc, score) in enumerate(scored, 1):
                    src = (getattr(doc, 'metadata', {}) or {}).get('source')
                    snip = (doc.page_content or "").replace("\n", " ")[:80]
                    print(f"      {i}. score={score}  src={src}  | {snip}")
            except Exception as qe:
                print(f"\n[4] Query {q!r} FAILED: {qe}")
except Exception as ex:
    print(f"\n[4] SEARCH ERROR: {ex}")

print("\n" + "=" * 60)
print("DONE - upar ka poora output copy karke bhej de")
print("=" * 60)
