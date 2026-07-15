# UPSC Agentic AI — Free Production Deployment Guide

Deploy the whole stack for **₹0 / month** with minimal maintenance.

**Target architecture**

| Layer | Service (free tier) | Why |
|---|---|---|
| Frontend (React/Vite SPA) | **Vercel** | Zero-config Vite, global CDN, `vercel.json` already present |
| Backend (FastAPI + LangGraph) | **Render** (free web) | `render.yaml` already present; stateless |
| Database | **Supabase Postgres** or **Neon** | Managed Postgres + connection pooler |
| Vector DB | **Qdrant Cloud** (1 GB) | App already supports it; no disk needed |
| Redis (cache/jobs) | **Upstash Redis** | REST cache + optional rq worker |
| LLM | **Google Gemini** (primary) + **Groq** (fallback) | Both free |
| Web search | **Tavily** (or built-in DuckDuckGo) | Free |
| Observability | **Langfuse** + **Sentry** | Both free |
| File/NCERT storage | **Supabase Storage** or bake into image | Free free-tier has no disk |

---

## Step 0 — Create the free accounts
Google AI Studio (Gemini key), Groq, Qdrant Cloud, Supabase (or Neon), Upstash, Render, Vercel, (optional) Tavily, Langfuse, Sentry.

## Step 1 — Provision the database
1. Supabase → New project → Database → **Connection string** → use the **Session pooler** URL (port **6543**).
2. Save it as `DATABASE_URL` (append `?sslmode=require`).

## Step 2 — Provision the vector DB
1. Qdrant Cloud → create a free 1 GB cluster → copy `QDRANT_URL` (`https://...:6333`) and `QDRANT_API_KEY`.

## Step 3 — Provision Redis (optional but recommended)
1. Upstash → create Redis DB → copy the **REST URL + token** → `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`.

## Step 4 — Get the API keys
`GOOGLE_API_KEY` (AI Studio), `GROQ_API_KEY` (Groq), optional `TAVILY_API_KEY`, `SENTRY_DSN`, `LANGFUSE_*`.
Generate `JWT_SECRET`: `python -c "import secrets;print(secrets.token_urlsafe(48))"`.

## Step 5 — Deploy the backend (Render)
1. Push the repo to GitHub.
2. Render → **New +** → **Blueprint** → select the repo (reads `render.yaml`).
3. In the service **Environment** tab set every `sync:false` secret from Step 1–4, plus:
   - `ENV=production`, `REQUIRE_EMAIL_VERIFICATION=false`
   - `CORS_ORIGINS=["https://YOUR-APP.vercel.app"]`  (JSON array!)
4. Deploy. Migrations run automatically (`alembic upgrade head`). Verify `https://<service>.onrender.com/health` returns `{"status":"healthy"}`.

> Prefer Docker? This bundle ships a backend `Dockerfile`; set Render runtime to Docker instead of Python, or deploy to **Fly.io** (`fly launch`) for an always-on free VM (no cold starts).

## Step 6 — Deploy the frontend (Vercel)
1. Vercel → **Add New Project** → import repo → set **Root Directory** = `frontend`.
2. Env var: `VITE_API_BASE=https://<service>.onrender.com/api/v1`.
3. Deploy. Vercel uses `frontend/vercel.json` (SPA rewrites) automatically.
4. Copy the Vercel domain back into the backend `CORS_ORIGINS` and redeploy the backend.

## Step 7 — Seed content (optional)
Run the ingest scripts locally against prod creds:
`uv run python scripts/ingest_mentor_kb.py` and `scripts/ingest_topper_md.py`.

## Step 8 — Keep it awake (optional)
Render free sleeps after 15 min idle. Add the included `keep-alive.yml` workflow, or a free UptimeRobot monitor on `/health`.

## Step 9 — Wire CI/CD
Copy `deploy.yml` to `.github/workflows/`. Add secrets: `RENDER_DEPLOY_HOOK`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`; variable `LIVE_BASE_URL`.

---

## Local production-like run
```bash
cp deploy/.env.example .env   # fill in keys
docker compose -f deploy/docker-compose.yml up --build
# API http://localhost:8000/health   •   Web http://localhost:8080
```

## Health checks
- `GET /health` → liveness/readiness (used by Render, Docker HEALTHCHECK, uptime monitors).
- `GET /` → metadata. `GET /docs` → Swagger.
