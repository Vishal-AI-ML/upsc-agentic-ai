---
title: UPSC AI Pro Backend
emoji: 🎓
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: FastAPI + LangGraph backend for UPSC AI Pro
---

<!-- The YAML block above is Hugging Face Spaces metadata for the Docker deploy.
     GitHub renders it as a small table; leave it in place so the HF Space build
     does not break. It is not part of the documentation. -->

<div align="center">

# UPSC Agentic AI

**A production-grade, retrieval-grounded AI mentor for UPSC Civil Services preparation — built on FastAPI, LangGraph, and a multi-agent supervisor architecture.**

Eight specialised agents behind one supervisor · hybrid RAG with RRF fusion, reranking and citation enforcement · an LLM-as-judge quality gate in CI · engineered to run on free-tier cloud with graceful degradation everywhere.

[Live App](https://upsc-ai-agentic.vercel.app/) · [API](https://upsc-agentic-ai-gtsj.onrender.com/) · [API Docs (Swagger)](https://upsc-agentic-ai-gtsj.onrender.com/docs) · [Health](https://upsc-agentic-ai-gtsj.onrender.com/health)

</div>

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Screenshots](#screenshots)
- [API Documentation](#api-documentation)
- [Production Hardening](#production-hardening)
- [Performance Metrics](#performance-metrics)
- [Security](#security)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)
- [Resume Value](#resume-value)

---

## Problem Statement

**The problem.** UPSC preparation spans years, a very large syllabus (NCERTs, standard texts, current affairs, previous-year questions), and requires constant answer-writing practice with feedback. Aspirants juggle disconnected tools: PDFs, coaching notes, YouTube lectures, a separate planner, and no reliable way to get grounded, syllabus-aware answers or objective feedback on mains answers.

**Why existing solutions fall short.**
- **Generic chatbots hallucinate.** A raw LLM will confidently invent article numbers, committee names, and dates — unacceptable for an exam where precision is everything.
- **No grounding or citations.** Most tools cannot show *where* an answer came from, so a serious aspirant cannot trust or verify it.
- **No feedback loop.** Reading model answers is not the same as having your own answer evaluated against criteria.
- **Cost and fragility.** Naive multi-agent RAG stacks are expensive and brittle; one slow vector DB or a rate-limited LLM takes the whole app down.

**Why this project was built.** To demonstrate that a genuinely useful, *grounded*, multi-agent study assistant can be built and **operated** under real constraints — free-tier hosting, a single web worker, and unreliable upstreams — without sacrificing correctness. Every answer is retrieved, fused, reranked, grounded with citations, and continuously graded by an LLM-as-judge gate in CI. The engineering goal was production behaviour (fail-open degradation, background work, tracing, rate limiting) rather than a demo that only works on a laptop.

---

## Features

### Core Features

| Feature | What it does | Backend |
|---|---|---|
| **Mentor Chat** | Conversational UPSC mentor with streaming responses, conversation memory, and a grounded knowledge base. | `src/agents/mentor`, `/mentor/chat` |
| **NCERT RAG** | Browse class → subject → chapter, then generate grounded notes, mind-maps, and practice questions from NCERT content. | `src/agents/ncert`, `/ncert/*` |
| **PDF Upload RAG** | Upload a PDF, process it into the vector store as a background job, then chat with the document. | `src/agents/upload`, `/upload/*` |
| **PYQ Generation** | Generate and parse previous-year-style questions by topic, plus a personal question bank. | `src/agents/pyq`, `/pyq/*` |
| **Planner** | Generates a structured, timeline-aware study plan (attempt year, months-left, sectioned schedule). | `src/agents/planner`, `/planner/*` |
| **Evaluator** | Grades prelims/mains answers into structured feedback (score, what went well, gaps, improvements). | `src/agents/evaluator`, `/evaluator/*` |
| **Current Affairs** | Daily, editorial, and monthly current-affairs digests ingested into retrieval. | `src/agents/current_affairs`, `/current-affairs/*` |
| **History** | Persistent conversation history and previous-session restore across agents. | `src/api/routes/history.py`, `/history/*` |

### Production Features

| Feature | Implementation |
|---|---|
| **Background workers** | DB-persisted, thread-backed job queue — long PDF/lecture work runs off the request path and survives restarts (`src/core/job_queue.py`). |
| **Semantic cache** | Two-stage response cache (exact SHA-256 key + optional embedding similarity), scoped per conversation, fail-open (`src/core/response_cache.py`). |
| **Circuit breakers** | Dependency-free breaker that trips flaky upstreams (e.g. Redis REST) to fail fast instead of hammering them (`src/core/circuit_breaker.py`). |
| **Distributed rate limiting** | Upstash-Redis fixed-window limiter with transparent in-process sliding-window fallback (`src/api/rate_limit_core.py`). |
| **Structured logging** | Centralised logging config with request-scoped context (`src/core/logging_config.py`, `src/core/request_context.py`). |
| **Request tracing** | Correlation IDs on every request/response and log line via outermost middleware (`src/api/request_id.py`); optional Langfuse tracing. |
| **Error recovery** | Global exception handler (clean JSON, no stack-trace leaks), stale-job reaping on boot, per-request hard timeout, Sentry hook. |

---

## Architecture

### High-level

```
         Browser (React + Vite SPA, Vercel)
                     |  HTTPS, JWT bearer
                     v
  FastAPI app  (src/api/main.py)
   middleware stack (outer -> inner):
   RequestId -> HttpMetrics -> MaxUploadSize -> RateLimit -> Timeout -> SecurityHeaders -> CORS
                     |
                     v
  Route modules (src/api/routes/*.py)  -- auth, per-feature, admin dashboards
                     |
                     v
  LangGraph Supervisor (src/graph/supervisor.py, app_graph.py)
                     |  routes to one sub-agent
     +---------------+-----------------------------------------+
     v               v                v            v           v
  Mentor        Evaluator         Planner        NCERT ...   Upload
  (src/agents/<agent>/graph.py + prompts.py)
                     |
                     v
  Shared core services (src/core/*.py)
   Retrieval (hybrid + RRF + rerank) -> Grounding/citations
   Model router (LITE/STRONG) -> LLM providers (Gemini -> Groq fallback)
   Vector store (Qdrant | Chroma fallback) | Postgres (state, history, checkpoints)
```

### Request flow
1. SPA calls `/<api_prefix>/...` with a JWT bearer token.
2. Middleware assigns a request ID, records metrics, enforces upload size + rate limits, applies a hard 90s timeout, and adds security headers.
3. `get_current_user` validates the JWT for every protected router.
4. The route hands off to the shared LangGraph app built once at startup (`app.state.agent_graph`).

### Agent flow
1. The **supervisor** inspects the request and routes to the correct sub-agent.
2. Each sub-agent is a self-contained LangGraph pipeline (`graph.py`) with its own prompts.
3. The **model router** (`model_router.py`) picks a **LITE** or **STRONG** tier per turn — biased toward STRONG when unsure (quality over cost).
4. Streaming routes push tokens as they are produced; `/sync` routes return Pydantic-validated structured output.

### RAG flow
1. **Query rewrite/expansion** (`retrieval.rewrite_query`).
2. **Hybrid retrieval** — dense vectors + lexical overlap.
3. **RRF fusion** (`reciprocal_rank_fusion`) merges ranked lists.
4. **Rerank** by concept coverage + overlap.
5. **Grounded compose** (`grounding.compose_grounded_answer`) with enforced citations and a confidence note. A relevance gate blocks off-syllabus answers.

### Background job flow
1. A heavy request (PDF/lecture) enqueues a job and returns a `job_id` immediately.
2. A thread-pool worker executes it; status + result are persisted in Postgres.
3. The client polls `GET /jobs/{job_id}` until `done`/`error`.
4. On boot, `reap_stale_jobs` flips orphaned `queued`/`running` rows to `error` so clients never hang on a dead job.

> A deeper write-up lives in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Tech Stack

| Layer | Choices |
|---|---|
| **Frontend** | React 18, TypeScript 5.5, Vite 5, React Router 6, TanStack Query 5, Recharts, `react-markdown` + `rehype-sanitize`, Tailwind CSS 3 |
| **Backend** | Python 3.13, FastAPI, Uvicorn, Pydantic v2 + `pydantic-settings`, SQLAlchemy 2, Alembic |
| **AI Stack** | LangGraph 1.x (supervisor + subgraphs + checkpointer), LangChain, Google Gemini (primary) with Groq fallback, Gemini embeddings, Tavily / DuckDuckGo web search |
| **Database** | PostgreSQL (Supabase/Neon pooled) for users, history, jobs, and LangGraph checkpoints; SQLite auto-fallback for local/tests |
| **Vector DB** | Qdrant (managed) with local Chroma fallback |
| **Infrastructure** | Upstash Redis (response cache + distributed rate limiting + job backend), Docker (multi-stage, non-root), uv for dependency management |
| **Observability** | Langfuse (LLM tracing), Sentry (error monitoring), structured logging, in-app HTTP metrics + admin monitoring dashboard |
| **Deployment** | Render (backend, Docker/Blueprint) · Vercel (frontend SPA) · Hugging Face Spaces (Docker) · GitHub Actions (CI) |

---

## Repository Structure

```
.
├─ src/                      # FastAPI + LangGraph backend (109 modules)
│  ├─ api/
│  │  ├─ main.py            # app factory, middleware stack, router registration
│  │  ├─ deps.py            # shared deps (current user, DB session)
│  │  ├─ rate_limit*.py     # distributed rate limiting (+ fallback)
│  │  ├─ security_headers.py# hardening headers + request timeout
│  │  ├─ request_id.py      # correlation-ID tracing middleware
│  │  └─ routes/            # 17 route modules (auth + per-feature + admin)
│  ├─ agents/               # 8 self-contained sub-agents (graph.py + prompts.py)
│  │  └─ mentor | evaluator | planner | pyq | ncert | lecture | current_affairs | upload
│  ├─ graph/                # supervisor, app_graph, RAG graph, tools, memory, state
│  ├─ core/                 # LLM, model router, retrieval, grounding, cache, jobs,
│  │                        # circuit breaker, security, db, config, observability
│  ├─ eval/                 # offline LLM-as-judge + retrieval-quality harness & gates
│  └─ schemas.py            # all Pydantic request/response contracts
├─ frontend/                 # React + Vite SPA (40 files)
│  ├─ src/                   # pages, features, components, lib
│  └─ dist/                  # production build output
├─ migrations/               # Alembic migrations (versions/0001..0003)
├─ tests/                    # 33 offline test modules (206 test functions)
├─ scripts/                  # KB ingestion + demo-user helpers
├─ screenshots/              # documentation screenshots (see below)
├─ Dockerfile                # backend production image (multi-stage, uv, non-root)
├─ docker-compose.yml        # local backend + deps
├─ render.yaml               # Render Blueprint (backend)
├─ alembic.ini               # migration config (URL resolved from settings)
├─ pyproject.toml            # backend deps + ruff config (uv-managed)
└─ .github/workflows/ci.yml  # CI: tests, build, nightly LLM-eval gate
```

---

## Quick Start

**Prerequisites:** Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js 20+.

### Clone

```bash
git clone https://github.com/<your-username>/upsc-agentic-ai.git
cd upsc-agentic-ai
```

### Backend setup

```bash
# 1. Install locked dependencies into an isolated venv
uv sync --frozen

# 2. Configure environment
cp .env.example .env
# edit .env: set JWT_SECRET and GOOGLE_API_KEY (minimum to boot).
# Generate a secret: python -c "import secrets;print(secrets.token_urlsafe(48))"

# 3. Apply database migrations (SQLite is used automatically if DATABASE_URL is empty)
uv run alembic upgrade head

# 4. Run the API (http://localhost:8000, docs at /docs)
uv run uvicorn src.api.main:app --reload
```

> Only `JWT_SECRET` and `GOOGLE_API_KEY` are strictly required to boot. Everything else (Postgres, Qdrant, Redis, Langfuse, Sentry, SMTP) is optional and **fails open** to a local/no-op fallback.

### Frontend setup

```bash
cd frontend
npm ci
cp .env.example .env.local          # set VITE API base URL if needed
npm run dev                          # http://localhost:5173
# production build:
npm run build                        # tsc -b && vite build -> dist/
```

---

## Environment Variables

Full reference in [`.env.example`](./.env.example). Required keys are marked; everything else has a safe default or a fail-open fallback.

| Variable | Required | Default | Purpose |
|---|:---:|---|---|
| `JWT_SECRET` | ✅ | — | Signing secret for JWT auth (32+ chars) |
| `GOOGLE_API_KEY` | ✅ | — | Primary LLM (Google Gemini) |
| `DATABASE_URL` | – | SQLite fallback | Postgres (use pooled/6543 URL on free tiers) |
| `GROQ_API_KEY` | – | — | Fallback LLM on Gemini 429 |
| `ENABLE_PROVIDER_FALLBACK` | – | `true` | Gemini → Groq failover |
| `QDRANT_URL` / `QDRANT_API_KEY` | – | Chroma fallback | Managed vector store |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | – | `gemini` | Embeddings (keep `gemini` on 512 MB tiers) |
| `SIMILARITY_THRESHOLD` / `MENTOR_KB_THRESHOLD` | – | `0.3` / `0.25` | Retrieval relevance gates |
| `TAVILY_API_KEY` | – | DuckDuckGo | Web search |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | – | in-process | Response cache + distributed rate limit |
| `REDIS_URL` / `JOBS_BACKEND` | – | `auto` | Background job backend |
| `RESPONSE_CACHE_ENABLED` | – | `true` | Toggle semantic/exact cache |
| `CORS_ORIGINS` | – | `[localhost:5173]` | JSON array of allowed origins |
| `RATE_LIMIT_REQUESTS` / `_PERIOD` | – | `100` / `60` | Global per-IP rate limit |
| `AUTH_RATE_LIMIT_REQUESTS` / `_PERIOD` | – | `10` / `300` | Stricter auth-endpoint limit |
| `MAX_UPLOAD_MB` | – | `20` | Upload size cap |
| `LANGFUSE_ENABLED` / keys | – | `false` | LLM tracing |
| `SENTRY_DSN` | – | — | Error monitoring |
| `SMTP_*` / `FRONTEND_URL` | – | — | Email verification + password reset |
| `REQUIRE_EMAIL_VERIFICATION` | – | `false` | Auto-disabled if SMTP unset |
| `ADMIN_EMAILS` | – | `[]` | Allowlist for cost/monitoring dashboards |
| `ENV` / `DEBUG` / `LOG_LEVEL` / `WEB_CONCURRENCY` | – | `production` / `false` / `INFO` / `1` | Runtime + security gates |

---

## Deployment

### GitHub
Push to `main`. GitHub Actions (`.github/workflows/ci.yml`) runs the offline quality gate (lint → compile → tests) and the frontend type-check + build on every push and PR. A nightly job runs the live LLM-as-judge faithfulness gate and a deploy smoke test.

### Render (backend)
Deploy via the included [`render.yaml`](./render.yaml) Blueprint (or Docker).

- **Build command:** `pip install uv && uv sync --frozen`
- **Start command:** `uv run alembic upgrade head && uv run uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/health`
- **Env vars:** set secrets (`JWT_SECRET`, `GOOGLE_API_KEY`, `DATABASE_URL`, `QDRANT_*`, `CORS_ORIGINS`, …) in the dashboard — never commit them (`sync: false` in the Blueprint).
- Stateless service (vectors in Qdrant, state in Postgres) → runs on the **free plan** with no persistent disk.

### Vercel (frontend)
Import the `frontend/` directory (config in [`frontend/vercel.json`](./frontend/vercel.json)).

- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Rewrites:** all routes → `/index.html` (SPA)
- Set the API base URL env var to your Render backend origin.

### Docker / Hugging Face Spaces
The multi-stage [`Dockerfile`](./Dockerfile) builds a slim, non-root image targeting `src.api.main:app` on port `7860`, with a container health check on `/health`. It runs `alembic upgrade head` before boot.

---

## Screenshots

Captured at 1920×1080 with Playwright, in light and dark themes. Full set + mapping in [`screenshots/README_SCREENSHOTS.md`](./screenshots/README_SCREENSHOTS.md).

| Dashboard | Mentor Chat |
|---|---|
| ![Dashboard](./screenshots/dashboard.png) | ![Mentor Chat](./screenshots/mentor-chat.png) |

| Planner | Evaluator |
|---|---|
| ![Planner](./screenshots/planner.png) | ![Evaluator](./screenshots/evaluator.png) |

| Upload RAG | Current Affairs |
|---|---|
| ![Upload RAG](./screenshots/upload-rag.png) | ![Current Affairs](./screenshots/current-affairs.png) |

---

## API Documentation

Interactive docs are served at `/docs` (Swagger) and `/redoc`. All routes are prefixed with the configured API prefix; every non-auth router requires a valid JWT bearer token. Selected endpoints:

### Authentication (`/auth`)
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (email verification when SMTP configured) |
| POST | `/auth/login` | Obtain access + refresh tokens |
| GET | `/auth/me` | Current user profile |
| POST | `/auth/refresh` | Rotate access token from refresh token |
| POST | `/auth/logout` | Invalidate refresh token |
| POST | `/auth/forgot-password` · `/auth/reset-password` | Password reset flow |
| POST | `/auth/verify-email` · `/auth/resend-verification` | Email verification |

### Agent APIs
| Method | Path | Description |
|---|---|---|
| POST | `/agent/chat/stream` | General streaming chat entry point |
| POST | `/mentor/chat` · `/mentor/chat/sync` | Mentor (streaming / structured) |
| POST | `/planner/generate` · `/planner/generate/sync` | Study plan (streaming / structured) |
| POST | `/evaluator/evaluate/sync` · `/mains/sync` · `/model-answer/sync` | Answer evaluation |
| GET/POST | `/ncert/classes` · `/subjects/{c}` · `/chapters/{c}/{s}` · `/study` · `/chat` | NCERT browse + RAG |
| POST/GET | `/pyq/generate` · `/parse` · `/topics/{type}` · `/bank/*` | PYQ generation + question bank |
| POST/GET | `/current-affairs/daily` · `/editorial` · `/monthly` · `/topics` · `/dates` · `/months` | Current affairs |

### Upload APIs
| Method | Path | Description |
|---|---|---|
| POST | `/upload/process` | Upload a PDF → enqueue processing job, returns `job_id` |
| POST | `/upload/chat` | Chat with the processed document |
| POST | `/lecture/process` · `/process-text` · `/chat` | Lecture ingestion + chat |
| GET | `/jobs/{job_id}` | Poll background job status/result |

### History APIs
| Method | Path | Description |
|---|---|---|
| GET | `/history/conversations` | List a user's conversations |
| GET | `/history/conversations/{id}/messages` | Restore a previous session's messages |
| POST | `/history/messages` | Persist a message |
| POST | `/feedback/submit` | Submit response feedback (fuels eval dataset) |

---

## Production Hardening

- **Background processing.** A DB-persisted, thread-backed job queue keeps long PDF/lecture work off the request path; job state survives web-process restarts, and stale jobs are reaped on boot so clients never poll forever. Backend is selectable (`thread` / `inline` / `auto`).
- **Circuit breakers.** A dependency-free breaker wraps flaky upstreams (e.g. the Upstash REST endpoint): after N consecutive failures it OPENS and fails fast for a cooldown, then probes HALF_OPEN before closing — no thundering-herd retries.
- **Distributed rate limiting.** An Upstash-Redis fixed-window counter enforces per-IP limits across instances, and transparently falls back to an in-process sliding window when Redis creds are unset, the breaker is open, or a call errors. Auth endpoints get a stricter limit.
- **Structured logging.** Centralised logging config with request-scoped context; each log line carries the correlation ID.
- **Request tracing.** `RequestIdMiddleware` is the outermost middleware — it honours an inbound `X-Request-ID` or generates one, threads it through logs, and returns it on the response. Optional Langfuse traces every LLM call.
- **Error recovery.** A global exception handler returns a clean JSON envelope (never a stack trace), a hard 90s per-request timeout prevents a stuck upstream from pinning the single free-tier worker, security headers are added to every response, and Sentry captures unhandled errors when configured.
- **CI/CD pipeline.** `.github/workflows/ci.yml`: on every push/PR → ruff lint + `compileall` + offline `pytest`, and a frontend type-check + `vite build`. Nightly (and on demand) → a live **LLM-as-judge** faithfulness gate (`--gate 0.9 --relevancy-gate 0.7 --precision-gate 0.6`) plus a retrieval-quality report and a deploy smoke test, with reports uploaded as artifacts.

---

## Performance Metrics

Only measured, reproducible numbers are listed. Latency/cold-start figures depend on the deployment tier and are intentionally **not** asserted as fixed benchmarks.

| Metric | Value | How to reproduce |
|---|---|---|
| Initial load (entry JS + CSS) | **244 KB raw ≈ 82 KB gzip** | `frontend/dist/assets/index-*.js` + `index-*.css` |
| Heaviest lazy chunk (charts, route-split to Dashboard/Cost) | 364 KB raw ≈ 100 KB gzip | `generateCategoricalChart-*.js` |
| Markdown/rendering chunk (lazy) | 159 KB raw ≈ 48 KB gzip | `Markdown-*.js` |
| Total built frontend output | 920 KB (`dist/`), code-split into 17 chunks | `du -sh frontend/dist` |
| Backend size | 15,455 LOC across 109 Python modules | `find src -name '*.py' \| xargs wc -l` |
| Frontend size | 6,243 LOC across 40 TS/TSX files | `find frontend/src -name '*.ts*' \| xargs wc -l` |
| Automated tests | **206 test functions in 33 offline modules** | `uv run pytest -q` |
| DB migrations | 3 Alembic revisions | `migrations/versions/` |
| Frontend build | `tsc -b && vite build` (type-check + bundle) | `cd frontend && npm run build` |

> **Latency, cold start, and CI build time:** the backend is deployed on Render's free plan, which sleeps on inactivity; a cold request pays a container wake-up + `alembic upgrade head` before serving. These vary by tier and are not benchmarked here — the response cache and LITE/STRONG model routing exist specifically to reduce warm-path latency and cost. Measure your own with the commands above.

---

## Security

- **JWT authentication.** Signed access tokens (`python-jose`) with expiry; short-lived access + rotating refresh tokens (`src/core/refresh_tokens.py`), and logout invalidation. Every protected router depends on `get_current_user`.
- **Password hashing.** `bcrypt` via `passlib` — no plaintext passwords are ever stored.
- **Rate limiting.** Global per-IP limit plus a stricter auth-endpoint limit, distributed via Redis with an in-process fallback (see Hardening).
- **Security headers.** `SecurityHeadersMiddleware` adds standard hardening headers to every response, with a relaxed CSP only on the docs paths so Swagger UI still loads.
- **Secrets management.** All secrets come from environment variables (`pydantic-settings`); `.env` is git-ignored and Render Blueprint secrets are `sync: false`. `src/core/secret_utils.py` avoids logging sensitive values. CORS is an explicit allowlist. Ownership checks ensure users can only read their own conversations/history (`tests/test_security_ownership.py`).
- **Prompt-injection defence.** Untrusted retrieved/uploaded content is sanitised and wrapped before it reaches the model (`src/core/prompt_safety.py`).

---

## Testing

```bash
uv run pytest -q          # 206 offline tests, no API key or network required
uv run ruff check src tests
cd frontend && npm run build && npm run lint
```

- **Unit tests.** Pure logic — model routing, RRF fusion, reranking, circuit breaker, rate limiter, eval parsing, plan timeline, secret utils, prompt safety.
- **Integration/smoke tests.** Boot the **real** FastAPI app against a throwaway SQLite DB and exercise critical paths (health, auth + email verification, relevance gate, PYQ parser, RAG citations, ownership). LLM/email/network calls are mocked, so the whole suite runs offline with no keys.
- **Quality-gate tests.** LLM-as-judge gate logic, retrieval-quality eval, and grounding/citation enforcement.
- **CI checks.** ruff lint, `compileall` syntax check, offline pytest, frontend type-check + build, prettier format check; nightly live faithfulness gate + deploy smoke test.
- **Linting/formatting.** ruff (`E`, `F`, `W`, `I`) for Python; Prettier for the frontend.

---

## Roadmap

### Completed
- Multi-agent supervisor with 8 specialised agents and streaming.
- Hybrid retrieval (dense + lexical) with RRF fusion, reranking, and citation enforcement.
- LLM-as-judge quality gate + retrieval-quality eval wired into CI.
- Provider fallback (Gemini → Groq), LITE/STRONG model routing.
- Background job queue, semantic response cache, circuit breaker, distributed rate limiting.
- Session history + previous-session restore, feedback → eval dataset loop, study streaks.
- Structured logging, request tracing, Langfuse + Sentry hooks, admin cost/monitoring dashboards.
- Docker image, Render Blueprint, Vercel SPA config, keep-alive-friendly stateless design.

### In Progress
- Advanced-RAG quality lift: cross-encoder reranking, multi-query retrieval (RAG-Fusion), HyDE.
- Human-in-the-loop via LangGraph interrupts; parallel fan-out in plan-execute.

### Future
- Spaced-repetition scheduler and weak-area analytics derived from PYQ performance.
- Consolidated mentor experience; an interview-simulator / mock-analysis agent.

---

## Contributing

Contributions are welcome.

1. Fork and create a branch: `git checkout -b feat/your-feature`.
2. Set up the backend and frontend (see [Quick Start](#quick-start)).
3. Keep changes focused and add/adjust tests. Run the full local gate before pushing:
   ```bash
   uv run ruff check src tests && uv run pytest -q
   cd frontend && npm run build && npm run lint
   ```
4. Use clear, conventional commit messages and open a PR describing the change and the tradeoffs.
5. CI must pass. For changes touching retrieval/prompts, note the impact on the eval gate.

Please open an issue first for large or architectural changes so we can align on approach.

---

## License

No license file is currently committed. **Recommended: MIT** — permissive, familiar to recruiters and contributors, and appropriate for a portfolio/product project. Add a `LICENSE` file:

```
MIT License — Copyright (c) 2026 Vishal Shivhare
```

If you prefer an explicit patent grant, choose **Apache-2.0** instead.

---

## Author

**Vishal Shivhare** — GenAI / Backend Engineer. Designer and primary maintainer of UPSC Agentic AI.

- GitHub: [github.com/&lt;your-username&gt;](https://github.com/)
- LinkedIn: [linkedin.com/in/&lt;your-handle&gt;](https://www.linkedin.com/)
- Portfolio: [&lt;your-portfolio-url&gt;](https://example.com)

_(Replace the placeholders above with your live links.)_

---

## Resume Value

This project is concrete evidence of the ability to **build and operate** a production AI system, not just prototype one:

- **Agentic AI & LangGraph** — a supervisor routing to 8 self-contained sub-agent graphs, with checkpointing, shared state, and conversation memory.
- **RAG engineering** — hybrid retrieval, RRF fusion, reranking, groundedness + citation enforcement, and an automated relevance gate.
- **Production AI engineering** — LLM provider fallback, complexity-based model routing (cost/quality tradeoff), semantic response caching, and continuous LLM-as-judge quality gating in CI.
- **FastAPI / backend** — clean HTTP layer, dependency-injected auth, Pydantic v2 contracts, SQLAlchemy + Alembic migrations, streaming and structured endpoints.
- **Distributed systems** — distributed rate limiting with graceful fallback, circuit breakers, a persisted background job queue, and stateless horizontal-scaling-friendly design.
- **Observability** — structured logging, request-ID tracing, Langfuse LLM traces, Sentry error monitoring, and an in-app metrics/monitoring dashboard.
- **DevOps** — multi-stage non-root Docker, uv-locked builds, Render Blueprint + Vercel config, GitHub Actions CI with offline gates and nightly live evals.

The throughline: every feature is paired with an **operational** decision — fail-open fallbacks, cost controls, and honest measurement — chosen deliberately for real free-tier constraints.
