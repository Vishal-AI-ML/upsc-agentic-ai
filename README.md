# UPSC AI Pro 🎓

> An agentic, retrieval-grounded AI study platform for UPSC Civil Services aspirants — 8 specialised agents, a RAG knowledge core, and a production observability stack. Built to be **cheap to run** (free-tier cloud + 8 GB dev box) and **honest** (every answer is grounded and evaluated).

**Live:** https://upsc-agentic-ai.onrender.com &nbsp;•&nbsp; **API docs:** `/docs` &nbsp;•&nbsp; **Health:** `/health`

---

## ✨ What it does

UPSC AI Pro is a multi-agent tutor. A LangGraph **supervisor** routes each question to the right specialist agent, which retrieves grounded context (NCERT, current affairs, past papers) and answers with **citations**. Mains answers are **evaluated** by an LLM-as-judge with a faithfulness gate — that Mains answer-evaluation loop is the product's moat.

### The 8 agents

| Agent | Role |
|---|---|
| **mentor** | General doubt-solving, concept explanations, study strategy |
| **planner** | Personalised study timelines via plan-and-execute |
| **ncert** | Grounded Q&A over NCERT textbooks (RAG) |
| **lecture** | Lecture / YouTube content summarisation + relevance gating |
| **current_affairs** | Fresh current-affairs synthesis with sources |
| **pyq** | Previous-year-question parsing and practice |
| **evaluator** | Mains answer evaluation (LLM-as-judge, rubric-scored) |
| **upload** | User PDF ingestion → chunk → embed → queryable |

---

## 🏗️ Architecture

```
              ┌──────────────────────────────────────────────┐
  Client ───▶ │  FastAPI (src/api/main.py : app)             │
              │   • JWT auth + refresh   • rate limiting      │
              │   • CORS  • global error handler → Sentry     │
              └───────────────┬──────────────────────────────┘
                              │
                     ┌────────▼─────────┐   response cache (Upstash)
                     │ LangGraph        │◀─ exact + semantic lookup
                     │ supervisor       │
                     └───┬───────────┬──┘
            route ───────┘           └─────── memory (per-thread profile)
              │
   ┌──────────▼───────────┐        ┌───────────────────────┐
   │ 8 specialist agents   │──RAG──▶│ Vector store          │
   │ (see table above)     │        │  Qdrant (prod) /      │
   └──────────┬───────────┘        │  Chroma (local)       │
              │                     └───────────────────────┘
     reflection + eval gate                 │
              │                        Gemini embeddings
     LLM: Gemini ▶ Groq fallback
              │
     traces ──▶ Langfuse    errors ──▶ Sentry
```

### RAG pipeline
- **Hybrid retrieval**: lexical arm (with query rewriting) + dense arm (Gemini embeddings), fused with **Reciprocal Rank Fusion (RRF)**, then **reranked**.
- **Groundedness**: a similarity threshold gates weak chunks; answers carry **citations** back to sources.
- **Backends**: Qdrant (managed, prod) when `QDRANT_URL` is set, else on-disk Chroma (local dev).

### Reliability layers
- **Reflection / self-critique** before finalising answers.
- **Plan-and-execute** for multi-step planning tasks.
- **LLM-as-judge eval** with a strict multi-metric + per-agent faithfulness gate (nightly in CI).
- **Response cache** (Upstash): exact-match **and** opt-in **semantic** (embedding-similarity) — paraphrases reuse one answer.

---

## 🧰 Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Uvicorn |
| Agents / orchestration | LangGraph + LangChain |
| LLMs | Google Gemini (primary) → Groq (fallback) |
| Embeddings | `models/gemini-embedding-001` |
| Vector DB | Qdrant (prod) / Chroma (local) |
| Relational DB | Postgres (Supabase) / SQLite (tests) |
| Migrations | Alembic |
| Cache | Upstash Redis (REST) |
| Observability | Langfuse (tracing) + Sentry (errors) |
| Auth | JWT access + refresh, email verification |
| Integrations | MCP server (stdio + streamable HTTP) |
| Tooling | `uv`, pytest, GitHub Actions CI |
| Hosting | Render (web service, free tier) |

---

## 📁 Project structure

```
src/
  api/
    main.py            # FastAPI app factory + lifespan (entrypoint: app)
    routes/            # auth, chat, mentor, planner, ncert, lecture,
                       # current_affairs, pyq, evaluator, upload, history, feedback
  agents/              # one package per specialist agent (graphs + prompts)
  graph/               # supervisor, rag_graph, state, profile, tools, reflection
  core/
    config.py          # pydantic-settings (all env config)
    vector_store.py    # embeddings + Qdrant/Chroma backend
    retrieval.py       # hybrid retrieval, query rewrite, rerank
    response_cache.py  # Upstash exact + semantic cache
    observability.py   # Langfuse wiring
    error_monitoring.py# Sentry wiring
    security.py, db.py, email_utils.py, rate_limit.py, ...
  eval/                # llm_eval, retrieval_eval, gates
  models/              # ORM + pydantic schemas
tests/                 # 29 test files, offline by default
migrations/            # Alembic
render.yaml            # Render blueprint
.github/workflows/ci.yml
```

---

## 🚀 Quickstart (local)

**Prereqs:** Python 3.13, [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Vishal-AI-ML/upsc-agentic-ai.git
cd upsc-agentic-ai
uv sync                       # install deps from uv.lock
cp .env.example .env          # then fill in the values below
uv run alembic upgrade head   # create DB tables
uv run uvicorn src.api.main:app --reload
```

Open http://localhost:8000/docs.

---

## 🔑 Environment variables

| Key | Required | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ | Gemini LLM + embeddings |
| `GROQ_API_KEY` | ⬜ | Fallback LLM on Gemini 429s |
| `DATABASE_URL` | ✅ | Postgres (Supabase) in prod; SQLite locally |
| `JWT_SECRET` | ✅ | Strong random string (**boot fails in prod if weak**) |
| `DEBUG` | ✅ prod | Must be `false` in prod |
| `QDRANT_URL` / `QDRANT_API_KEY` | ⬜ | Enables Qdrant; else local Chroma |
| `CORS_ORIGINS` | ✅ prod | Include your deployed frontend origin |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | ⬜ | Email verification / password reset |
| `TAVILY_API_KEY` | ⬜ | Web search for current affairs |
| **Cache** | | |
| `RESPONSE_CACHE_ENABLED` | ⬜ | Default `false`; set `true` to turn on |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | ⬜ | Upstash creds |
| `RESPONSE_CACHE_SCOPE` | ⬜ | `thread` (default) / `user` / `global` |
| `RESPONSE_CACHE_TTL_SECONDS` | ⬜ | Default `86400` (24h) |
| `RESPONSE_CACHE_SEMANTIC` | ⬜ | Default `false`; embedding-similarity fallback |
| `RESPONSE_CACHE_SEMANTIC_THRESHOLD` | ⬜ | Cosine hit threshold, default `0.92` |
| **Observability** | | |
| `LANGFUSE_ENABLED` | ⬜ | Default `true` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | ⬜ | `pk-lf-…` / `sk-lf-…` |
| `LANGFUSE_HOST` | ⬜ | EU `https://cloud.langfuse.com` · US `https://us.cloud.langfuse.com` (must match signup region) |
| `SENTRY_DSN` | ⬜ | Enables Sentry error capture |
| `SENTRY_ENVIRONMENT` | ⬜ | e.g. `production` |
| `SENTRY_TRACES_SAMPLE_RATE` | ⬜ | Default `0.0` |

> ⚠️ Never commit real secrets. Rotate any credential that has ever been shared in plaintext.

---

## 🧪 Testing

```bash
uv run pytest -q                       # full offline suite (no API key needed)
```

- Tests boot the **real** FastAPI app against a throwaway SQLite DB; LLM, email and network calls are mocked → fully offline and deterministic.
- **Live smoke test** (opt-in, hits the deployed URL):

```bash
LIVE_BASE_URL=https://upsc-agentic-ai.onrender.com uv run pytest tests/test_smoke_live.py -q
```

---

## ☁️ Deployment (Render)

Managed by `render.yaml` (Blueprint). Start command:

```bash
uv run alembic upgrade head && uv run uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

1. **New → Web Service** → connect the repo (Blueprint auto-detected) → **Free** plan.
2. Add all env vars from the table above (Gemini, Groq, Supabase `DATABASE_URL`, Qdrant, `JWT_SECRET`, Upstash, Langfuse, Sentry, `DEBUG=false`).
3. Deploy → verify boot logs show `📊 Langfuse: True` and `🚨 Sentry: True`.
4. **Keep-alive:** free instances sleep after 15 min idle (~1 min cold start). A [cron-job.org](https://cron-job.org) job pings `/health` every 10 minutes (`*/10 * * * *`) to keep it warm.

---

## 📊 Observability

| Tool | Purpose | Why |
|---|---|---|
| **Upstash Redis** | Response cache | Cuts repeat latency + LLM cost; free 256 MB |
| **Langfuse** | LLM tracing / analytics | See every prompt, token, cost, and agent trace |
| **Sentry** | Error monitoring | Real-time crash alerts with stack traces |

All three **fail open** — if unconfigured or unreachable, the app runs exactly as before.

---

## 🔌 MCP server

The platform exposes its tools over the **Model Context Protocol** (stdio + streamable HTTP), so external MCP clients can use the UPSC tools directly. Toggle via `MCP_ENABLED` / `MCP_TRANSPORT` / `MCP_HTTP_PATH`.

---

## 🔁 CI/CD (GitHub Actions)

- **On every push/PR:** offline quality gate — `uv sync --frozen`, `py_compile` of AI modules, full `pytest -q`.
- **Nightly (02:00 UTC) / manual:** live **LLM-as-judge** faithfulness gate (`--gate 0.9`, strict multi-metric + per-agent) + retrieval-quality eval, both uploaded as artifacts.
- **Nightly / manual:** **live deploy smoke test** against `LIVE_BASE_URL`.

---

## 🗺️ Status

Production roadmap #1–#13 shipped: advanced evals, structured outputs, retrieval eval, security + ownership, migrations, reflection, plan-and-execute, RRF fusion + citations, MCP server, Upstash cache (exact + semantic), Langfuse, Sentry, Render deploy + keep-alive.

---

## 📜 License

Proprietary — all rights reserved (update this section if you intend to open-source).
