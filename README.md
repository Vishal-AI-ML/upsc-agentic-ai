<div align="center">

# UPSC AI Pro 🎓

**An agentic, retrieval-grounded AI study platform for UPSC Civil Services aspirants.**

8 specialised agents · a RAG knowledge core · a production observability stack — built to be *cheap to run* (free-tier cloud + 8 GB dev box) and *honest* (every answer is grounded and evaluated).

[![CI](https://github.com/Vishal-AI-ML/upsc-agentic-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Vishal-AI-ML/upsc-agentic-ai/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Uvicorn-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-LangChain-1C3C3C?logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/LLM-Gemini%20%E2%86%92%20Groq-4285F4?logo=googlegemini&logoColor=white)
![Tests](https://img.shields.io/badge/tests-180%20passing-brightgreen)
![License](https://img.shields.io/badge/license-Proprietary-lightgrey)

### 🌐 [Live App](https://upsc-agentic-ai.vercel.app) &nbsp;·&nbsp; ⚙️ [API](https://upsc-agentic-ai.onrender.com) &nbsp;·&nbsp; 📖 [API Docs](https://upsc-agentic-ai.onrender.com/docs) &nbsp;·&nbsp; ❤️ [Health](https://upsc-agentic-ai.onrender.com/health)

</div>

---

## 📑 Table of Contents

- [Why this exists](#-why-this-exists)
- [What it does](#-what-it-does)
- [The 8 agents](#-the-8-agents)
- [Architecture](#️-architecture)
- [How the RAG pipeline works](#-how-the-rag-pipeline-works)
- [Reliability & AI-quality layers](#-reliability--ai-quality-layers)
- [Tech stack](#-tech-stack)
- [Project structure](#-project-structure)
- [Quickstart (local)](#-quickstart-local)
- [Environment variables](#-environment-variables)
- [Testing](#-testing)
- [Deployment](#️-deployment)
- [Observability](#-observability)
- [MCP server](#-mcp-server)
- [CI/CD](#-cicd)
- [Roadmap](#️-roadmap)
- [License](#-license)

---

## 🎯 Why this exists

UPSC preparation drowns aspirants in scattered material — NCERTs, current affairs, past papers, and Mains answer practice with no fast feedback. **UPSC AI Pro** puts all of that behind one tutor that answers *with sources*, evaluates Mains answers like a real examiner, and runs on **free-tier infrastructure** so it stays sustainable.

> The **Mains answer-evaluation loop** (LLM-as-judge, rubric-scored, faithfulness-gated) is the product's moat — it's the hardest thing to get right and the most valuable to an aspirant.

---

## ✨ What it does

A LangGraph **supervisor** routes each question to the right specialist agent. The agent retrieves grounded context (NCERT / current affairs / past papers), answers **with citations**, self-critiques via a reflection pass, and — for Mains — is scored by an LLM-as-judge behind a faithfulness gate.

```
"Explain Article 21 with case laws"  →  supervisor  →  mentor + RAG  →  grounded answer + citations
"Evaluate my answer on federalism"   →  supervisor  →  evaluator     →  rubric score + feedback
"Make me a 30-day History plan"      →  supervisor  →  planner       →  plan-and-execute timeline
```

---

## 🤖 The 8 agents

| Agent | Role |
|-------|------|
| **mentor** | General doubt-solving, concept explanations, study strategy |
| **planner** | Personalised study timelines via plan-and-execute |
| **ncert** | Grounded Q&A over NCERT textbooks (RAG) |
| **lecture** | Lecture / YouTube summarisation + relevance gating |
| **current_affairs** | Fresh current-affairs synthesis with sources |
| **pyq** | Previous-year-question parsing and practice |
| **evaluator** | Mains answer evaluation (LLM-as-judge, rubric-scored) |
| **upload** | User PDF ingestion → chunk → embed → queryable |

---

## 🏗️ Architecture

```text
              ┌────────────────────────────────────────────┐
  Client ───▶ │  FastAPI (src/api/main.py : app)             │
  (Vercel     │   • JWT auth + refresh   • rate limiting      │
   frontend)  │   • CORS  • global error handler → Sentry     │
              └───────────────┬──────────────────────────┘
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

---

## 🔎 How the RAG pipeline works

1. **Hybrid retrieval** — a lexical arm (with query rewriting) **plus** a dense arm (Gemini embeddings).
2. **Fusion** — both arms are merged with **Reciprocal Rank Fusion (RRF)**.
3. **Rerank** — the fused set is reranked for final relevance.
4. **Groundedness gate** — a similarity threshold drops weak chunks; the answer carries **citations** back to its sources.
5. **Backend** — Qdrant (managed) when `QDRANT_URL` is set, else on-disk **Chroma** for local dev.

---

## 🛡️ Reliability & AI-quality layers

| Layer | What it buys you |
|-------|------------------|
| **Reflection / self-critique** | The model reviews its own draft before returning it |
| **Plan-and-execute** | Robust multi-step reasoning for planning tasks |
| **LLM-as-judge eval** | Nightly faithfulness gate (strict, multi-metric, per-agent) |
| **Retrieval eval** | Separate retrieval-quality report (precision / relevancy) |
| **Response cache** | Exact **and** opt-in **semantic** (embedding-similarity) reuse |
| **Fail-open everywhere** | Cache / tracing / monitoring never break a request |

---

## 🧰 Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Deployed on **Vercel** ([upsc-agentic-ai.vercel.app](https://upsc-agentic-ai.vercel.app)) |
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
| Hosting | Render (API, free tier) + Vercel (frontend) |

---

## 📁 Project structure

```text
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
upsc-frontend/         # web client (deployed to Vercel)
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

Open <http://localhost:8000/docs>.

---

## 🔑 Environment variables

### Core (required)

| Key | Notes |
|-----|-------|
| `GOOGLE_API_KEY` | Gemini LLM + embeddings |
| `DATABASE_URL` | Postgres (Supabase) in prod; SQLite locally |
| `JWT_SECRET` | Strong random string — **boot fails in prod if weak** |
| `DEBUG` | Must be `false` in prod |
| `CORS_ORIGINS` | Include your deployed frontend origin (the Vercel URL) |

### Optional — models & retrieval

| Key | Notes |
|-----|-------|
| `GROQ_API_KEY` | Fallback LLM on Gemini 429s |
| `QDRANT_URL` / `QDRANT_API_KEY` | Enables Qdrant; else local Chroma |
| `TAVILY_API_KEY` | Web search for current affairs |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Email verification / password reset |

### Optional — response cache (Upstash)

| Key | Notes |
|-----|-------|
| `RESPONSE_CACHE_ENABLED` | Default `false`; set `true` to turn on |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Upstash creds |
| `RESPONSE_CACHE_SCOPE` | `thread` (default) / `user` / `global` |
| `RESPONSE_CACHE_TTL_SECONDS` | Default `86400` (24h) |
| `RESPONSE_CACHE_SEMANTIC` | Default `false`; embedding-similarity fallback |
| `RESPONSE_CACHE_SEMANTIC_THRESHOLD` | Cosine hit threshold, default `0.92` |

### Optional — observability

| Key | Notes |
|-----|-------|
| `LANGFUSE_ENABLED` | Default `true` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | `pk-lf-…` / `sk-lf-…` |
| `LANGFUSE_HOST` | EU `https://cloud.langfuse.com` · US `https://us.cloud.langfuse.com` (must match signup region) |
| `SENTRY_DSN` | Enables Sentry error capture |
| `SENTRY_ENVIRONMENT` | e.g. `production` |
| `SENTRY_TRACES_SAMPLE_RATE` | Default `0.0` |

> ⚠️ **Never commit real secrets.** Rotate any credential that has ever been shared in plaintext.

---

## 🧪 Testing

```bash
uv run pytest -q                 # full offline suite (no API key needed)
```

- Tests boot the **real** FastAPI app against a throwaway SQLite DB; LLM, email and network calls are mocked → fully offline and deterministic.
- **Live smoke test** (opt-in, hits the deployed URL, absorbs cold starts):

```bash
LIVE_BASE_URL=https://upsc-agentic-ai.onrender.com uv run pytest tests/test_smoke_live.py -q
```

---

## ☁️ Deployment

**API → Render** (managed by `render.yaml` blueprint). Start command:

```bash
uv run alembic upgrade head && uv run uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

1. **New → Web Service** → connect the repo (Blueprint auto-detected) → **Free** plan.
2. Add all env vars above (Gemini, Groq, Supabase `DATABASE_URL`, Qdrant, `JWT_SECRET`, Upstash, Langfuse, Sentry, `DEBUG=false`).
3. Deploy → verify boot logs show `📊 Langfuse: True` and `🚨 Sentry: True`.
4. **Keep-alive:** free instances sleep after 15 min idle (~1 min cold start). A [cron-job.org](https://cron-job.org) job pings `/health` every 10 minutes (`*/10 * * * *`) to keep it warm.

**Frontend → Vercel** ([upsc-agentic-ai.vercel.app](https://upsc-agentic-ai.vercel.app)) — point its API base URL at the Render service and add that origin to `CORS_ORIGINS`.

---

## 📊 Observability

| Tool | Purpose | Why |
|------|---------|-----|
| **Upstash Redis** | Response cache | Cuts repeat latency + LLM cost; free 256 MB |
| **Langfuse** | LLM tracing / analytics | See every prompt, token, cost, and agent trace |
| **Sentry** | Error monitoring | Real-time crash alerts with stack traces |

All three **fail open** — if unconfigured or unreachable, the app runs exactly as before.

---

## 🔌 MCP server

The platform exposes its tools over the **Model Context Protocol** (stdio + streamable HTTP), so external MCP clients can call the UPSC tools directly. Toggle via `MCP_ENABLED` / `MCP_TRANSPORT` / `MCP_HTTP_PATH`.

---

## 🔁 CI/CD

| Trigger | What runs |
|---------|-----------|
| Every push / PR | Offline quality gate — `uv sync --frozen`, `py_compile` of AI modules, full `pytest -q` |
| Nightly (02:00 UTC) / manual | Live **LLM-as-judge** faithfulness gate (`--gate 0.9`, strict multi-metric + per-agent) + retrieval-quality eval (artifacts uploaded) |
| Nightly / manual | **Live deploy smoke test** against `LIVE_BASE_URL` |

---

## 🗺️ Roadmap

Production roadmap #1–#13 — **all shipped & live**:

- [x] Advanced evals + structured outputs
- [x] Retrieval eval
- [x] Security + row-level ownership
- [x] Alembic migrations
- [x] Reflection / self-critique
- [x] Plan-and-execute
- [x] RRF fusion + citations
- [x] MCP server (stdio + HTTP)
- [x] Upstash cache — exact **and** semantic
- [x] Langfuse tracing
- [x] Sentry monitoring
- [x] Render deploy + keep-alive cron
- [x] Live e2e smoke test in CI

**Next up (nice-to-have):** distributed rate limiting (Upstash-backed) · deprecation cleanup · frontend refresh-token wiring → shorter access-token TTL.

---

## 📜 License

Proprietary — all rights reserved. *(Update this section if you intend to open-source.)*

<div align="center">

Built with ❤️ for UPSC aspirants.

</div>
