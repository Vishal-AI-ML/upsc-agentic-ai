# UPSC AI Pro — RAG + Agentic Upgrades (audit #1–#5 + security)

Saare upgrades **config-gated** hain aur **default OFF + fail-open** — yaani jab tak
tum `.env` mein flag ON nahi karte, app ka behaviour bilkul pehle jaisa rehta hai.
Kisi bhi optional library / API key ke bina bhi kuch crash nahi hoga (purane path
pe transparently gir jaata hai).

> Ek hi baar file badli gayi hai. Feature ON/OFF sirf `.env` se hota hai —
> code dobara chhune ki zaroorat nahi.

---

## Kaunsi files badli

| File | Kya juda |
|------|----------|
| `src/core/config.py` | Naye flags (rerank / multi-query / hyde / hitl / parallel), `ENV` var, CORS wildcard guard |
| `src/core/retrieval.py` | `cross_encoder_rerank`, `expand_queries` (multi-query), `generate_hypothetical_document` (HyDE) |
| `src/core/vector_store.py` | `gather_scored_documents` (multi-query + HyDE merge) + cross-encoder pass wiring |
| `src/graph/agent_subgraphs.py` | Planner/Evaluator me Human-in-the-Loop `interrupt` |
| `src/graph/plan_execute.py` | Sub-steps ka parallel (concurrent) execution |
| `tests/test_advanced_retrieval.py` | Naye helpers ke fail-open unit tests |

---

## 1. Cross-Encoder Reranking
RRF fusion ke baad ek cross-encoder (query+chunk saath padhke) precise score deta hai.
```env
RERANK_ENABLED=true
RERANK_PROVIDER=local            # local | cohere
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANK_TOP_N=5
# provider=cohere ke liye:
# COHERE_API_KEY=xxxx
# COHERE_RERANK_MODEL=rerank-english-v3.0
```
Local ke liye: `uv add sentence-transformers` · Cohere ke liye: `uv add cohere`
(dependency na ho to fail-open → RRF order rehta hai.)

## 2. Multi-Query Retrieval (RAG-Fusion)
LLM query ko 2–4 tarike se likhta hai, sabse search hota hai, pool merge hota hai.
```env
MULTI_QUERY_ENABLED=true
MULTI_QUERY_COUNT=3              # original + paraphrases
```

## 3. HyDE (Hypothetical Document Embeddings)
Search se pehle ek fake answer generate karke usko embed karta hai.
```env
HYDE_ENABLED=true               # ek extra LLM call/query — free-tier pe soch ke
```

## 4. Human-in-the-Loop
Planner/Evaluator missing params (goal/hours, marks/word_limit) ke liye pause karta hai.
```env
HITL_ENABLED=true               # checkpointer + resume-capable client chahiye
```
Graph ko checkpointer ke saath compile karo; client `interrupt` payload padhke
`Command(resume={...})` bhejta hai.

## 5. Parallel Execution
Plan-execute ke independent sub-steps ek saath chalte hain.
```env
PLAN_EXECUTE_ENABLED=true
PLAN_EXECUTE_PARALLEL=true
PLAN_EXECUTE_MAX_CONCURRENCY=3
```

---

## Security fixes

| Item | Status |
|------|--------|
| **CORS wildcard** | `config.py` ab `"*"` origin ko credentials ke saath auto-drop karta hai + warn |
| **JWT prod-detection** | Naya `ENV` var (`ENV=production`) authoritative hai; `debug` flag pe depend nahi. Set `ENV=production` in prod |
| **/jobs/{id} IDOR** | Is version me owner-check pehle se maujood hai (`rec.user_id != user.id → 404`) — koi change zaroori nahi |
| **Upload memory** | Live route (`src/api/routes/upload.py`) me `%PDF-` magic-check + size cap pehle se hai — koi change zaroori nahi |

> Note: audit ki security list purane snapshot pe based thi. Is codebase me jobs-IDOR
> aur upload-size dono already fix hain, isliye maine sirf genuinely-missing do
> (CORS guard + explicit ENV) add kiye — bewajah code nahi chhua.

---

## Rollback
Sab kuch flag se off ho jaata hai — koi bhi `*_ENABLED=false` set karo (ya hata do),
behaviour pehle jaisa. Files revert karne ki zaroorat nahi.
