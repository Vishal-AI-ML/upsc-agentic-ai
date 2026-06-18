# 🎓 UPSC Agentic AI

> An AI-powered study companion for UPSC Civil Services aspirants — built as a team of specialist AI "agents" that plan, teach, quiz, evaluate, and mentor, all grounded in real study material.

**Live App:** `upsc-agentic-ai.vercel.app` &nbsp;•&nbsp; **API:** `upsc-agentic-ai.onrender.com/docs`

---

## 📖 What is this? (in plain English)

Imagine a single app where a UPSC student can:

- 📅 Get a **personalised study plan** ("I have 8 months and 6 hours/day")
- 📺 Paste a **YouTube lecture** and instantly get exam-ready notes + chat with it
- 📚 Open any **NCERT chapter** and get notes or ask doubts
- 📄 **Upload their own PDF** (book/notes) and study from it
- 📰 Read **daily / monthly current affairs** in an exam format
- ❓ Generate and practise **previous-year-style questions (PYQs)**
- ✍️ Get their **Mains answers graded** like a real examiner
- 🧑‍🏫 Ask a friendly **AI mentor ("Arjun")** any doubt, anytime

Under the hood, instead of one big AI trying to do everything, the system uses a **team of small expert AIs** (called *agents*). A **"manager" AI (the Supervisor)** reads each message and forwards it to the right expert — exactly like a front-desk receptionist routing you to the right department.

---

## 🗺️ The Big Picture

```mermaid
flowchart TD
    U["👤 Student"] --> FE["🌐 Web App<br/>(HTML frontend on Vercel)"]
    FE -->|"login + question"| API["⚙️ Backend API<br/>(FastAPI on Render)"]
    API --> SUP["🧭 Supervisor<br/>(decides which expert)"]

    SUP --> M["🧑‍🏫 Mentor"]
    SUP --> P["📅 Planner"]
    SUP --> E["✍️ Evaluator"]
    SUP --> CA["📰 Current Affairs"]
    SUP --> R["📚 Document Q&A (RAG)"]

    R --> NC["NCERT"]
    R --> LE["YouTube Lecture"]
    R --> UP["Uploaded PDF"]
    R --> PQ["PYQ Bank"]

    M & P & E & CA & R --> LLM["🤖 AI Brain<br/>(Gemini → Groq fallback)"]
    R --> VDB["🔎 Vector Search<br/>(Qdrant)"]

    API --> DB[("🗄️ Database<br/>Supabase Postgres<br/>users • history • memory")]

    classDef store fill:#eef,stroke:#88a;
    class VDB,DB store;
```

**How to read this:** a student talks to the web app → the backend's *Supervisor* picks the right expert → the expert thinks using the *AI Brain* (and, when needed, looks things up in stored notes via *Vector Search*) → the answer and chat history are saved in the *Database*.

---

## 🧭 How the Supervisor routes a message

Every message first hits the Supervisor, which classifies it into exactly one specialist. If it's unsure, it safely defaults to the **Mentor**.

```mermaid
flowchart TD
    START(["Student message"]) --> SUP{"🧭 Supervisor<br/>What is this about?"}
    SUP -->|"doubt / advice / chat"| M["🧑‍🏫 Mentor"]
    SUP -->|"make a study plan"| P["📅 Planner"]
    SUP -->|"grade my answer"| E["✍️ Evaluator"]
    SUP -->|"news / editorials"| CA["📰 Current Affairs"]
    SUP -->|"about a specific doc"| R["📚 RAG (NCERT/Lecture/PDF/PYQ)"]
    M --> OUT(["Answer"])
    P --> OUT
    E --> OUT
    CA --> OUT
    R --> OUT
```

> 💡 The UI can also *force* a route directly (e.g. the "Planner" tab skips the guessing step and goes straight to the Planner).

---

## 🧑‍🏫 Inside the Mentor ("Arjun")

The Mentor is the most-used agent. It first understands the *type* of message, then decides whether it needs to look anything up before answering.

```mermaid
flowchart LR
    Q(["Question"]) --> RT["🧠 Router<br/>casual? vague?<br/>emotional? academic?"]
    RT --> KB["📔 Look up trusted<br/>knowledge base"]
    KB --> DEC{"Needs live<br/>current facts?"}
    DEC -->|"Yes (dates, results,<br/>cut-offs, news)"| WEB["🌍 Web Search"]
    DEC -->|"No"| GEN["✍️ Write answer"]
    WEB --> GEN
    GEN --> A(["Mentor reply"])
```

**Why this matters:** the Mentor *never guesses* volatile facts like exam dates or cut-offs. If it doesn't have live data, it honestly tells the student to verify at `upsc.gov.in` instead of inventing a date. Stable facts (exam pattern, syllabus) come from a curated, verified knowledge base.

---

## 📚 Document Q&A with self-correction (CRAG)

NCERT, Lecture, Uploaded PDFs and the PYQ bank all share **one smart retrieval engine**. It retrieves relevant chunks of the document, then *grades itself*: if the retrieved text can't really answer the question, it falls back to a web search instead of bluffing. This pattern is called **Corrective RAG (CRAG)**.

```mermaid
flowchart TD
    Q(["Question about a document"]) --> RET["🔎 Retrieve relevant chunks<br/>(Qdrant vector search)"]
    RET --> GR{"🧪 Self-grade:<br/>Is this enough<br/>to answer?"}
    GR -->|"Yes"| GEN["✍️ Answer ONLY from<br/>the document"]
    GR -->|"No"| WEB["🌍 Web search fallback"]
    WEB --> GEN
    GEN --> A(["Grounded answer<br/>+ Prelims & Mains angle"])
```

---

## 📺 YouTube Lecture pipeline

```mermaid
flowchart LR
    URL(["YouTube URL"]) --> T["📥 Fetch transcript<br/>(via rotating proxy)"]
    T --> TOP["🏷️ Detect topic +<br/>GS paper + content type"]
    TOP --> N["📝 Generate exam notes<br/>(Groq / Gemini)"]
    N --> RESP(["Notes returned to student ✅"])
    N -.->|"in background"| IDX["🔧 Build chat index<br/>(embeddings → Qdrant)"]
    IDX -.-> CHAT(["💬 Chat with the lecture"])
```

> ⚙️ **Design choice:** notes are returned to the student *immediately*; the heavier chat-index build runs **in the background** so a slow embedding step never blocks (or crashes) the notes response. If embeddings hit a rate limit, notes are unaffected — only "chat with this lecture" waits.

---

## 🤖 The AI Brain: automatic provider fallback

The app is not locked to one AI provider. Every call tries the best model first and automatically falls over to the next if one is rate-limited (HTTP 429) or down — so the app keeps working on free tiers.

```mermaid
flowchart LR
    subgraph MAIN["Main chain (quality first)"]
        G1["Gemini 2.5 Flash"] -->|"fails / 429"| G2["Gemini 2.5 Flash-Lite"] -->|"fails / 429"| GQ["Groq Llama 3.3 70B"]
    end
    subgraph FAST["Fast chain (cheap first)"]
        F1["Gemini Flash-Lite"] -->|"fails"| F2["Groq Llama 3.1 8B"] -->|"fails"| F3["Gemini Flash"]
    end
```

- **Main chain** → notes, current affairs, mentor, planner, evaluator (quality matters).
- **Fast chain** → routing, topic detection, mind-maps, quick classification (speed/cost matters).
- **Embeddings** → currently Google `gemini-embedding-001`, with batching + exponential backoff on rate limits.

---

## 🧩 The Agents at a glance

| Agent | What it does | Grounded on |
|-------|--------------|-------------|
| 🧑‍🏫 **Mentor** | Doubts, concept explanations, strategy, motivation | Verified KB + live web (for volatile facts) |
| 📅 **Planner** | Personalised, hour-by-hour study plan | Live exam date + topper-strategy KB |
| ✍️ **Evaluator** | Grades Mains/basic answers like a real examiner | The student's own answer (no padding) |
| 📰 **Current Affairs** | Daily news, editorials, monthly digest | Live retrieved headlines (strict anti-hallucination) |
| 📚 **NCERT** | Notes + chat for NCERT chapters | The chapter text only |
| 📺 **Lecture** | YouTube → notes + chat | The video transcript only |
| 📄 **Upload** | Study from a user's own PDF | The uploaded document only |
| ❓ **PYQ** | Generate / parse / explain practice questions | Real PYQ patterns + fact-check pass |

**Common design principle across all agents:** *honesty over padding.* Every prompt explicitly forbids inventing facts, dates, names, or "this appeared in UPSC 20XX" claims. When in doubt, the agent says so.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Orchestration** | LangGraph (supervisor + subgraphs, shared state) |
| **LLMs** | Google Gemini 2.5 (Flash / Flash-Lite), Groq Llama 3.x (fallback) |
| **Embeddings** | Google `gemini-embedding-001` (local model planned for scale) |
| **Vector DB** | Qdrant (managed; local Chroma fallback for dev) |
| **Backend** | FastAPI (Python 3.13), JWT auth, rate limiting |
| **Database** | Supabase Postgres (users, history, LangGraph memory) |
| **Speech-to-text** | Groq Whisper (audio lecture upload) |
| **Web search** | Tavily (trusted-domain filtered) + DuckDuckGo fallback |
| **Observability** | Langfuse (end-to-end tracing) |
| **Frontend** | Static HTML/JS (Vercel) |
| **Hosting** | Render (API) + Vercel (frontend) + Qdrant Cloud + Supabase |

---

## 🚀 Getting Started (for developers)

### 1. Prerequisites
- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) package manager
- A Google AI Studio key (free) — minimum to run

### 2. Install
```bash
git clone https://github.com/Vishal-AI-ML/upsc-agentic-ai.git
cd upsc-agentic-ai
pip install uv
uv sync
```

### 3. Configure
Create a `.env` file in the project root:
```env
# --- Minimum to run ---
GOOGLE_API_KEY=your_google_ai_studio_key

# --- Recommended (free) fallback + features ---
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key

# --- Production stores (optional locally; app falls back to SQLite + Chroma) ---
DATABASE_URL=postgresql://user:pass@host:5432/postgres?sslmode=require
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_key
JWT_SECRET=a_long_random_secret

# --- Optional tuning ---
REQUIRE_EMAIL_VERIFICATION=false
EMBED_BATCH_SIZE=50
MAX_INDEX_CHUNKS=400
```
> 🔒 Without `DATABASE_URL`/`QDRANT_URL`, the app still runs locally using SQLite + on-disk Chroma. Without `GROQ_API_KEY`, it runs Gemini-only.

### 4. Run
```bash
uv run uvicorn src.api.main:app --reload
# API docs:    http://localhost:8000/docs
# Health:      http://localhost:8000/health
```

### 5. (Optional) Build the Mentor knowledge base
```bash
python scripts/ingest_mentor_kb.py
```

---

## 📁 Project Structure

```
src/
├── api/                FastAPI app + routes (one router per feature)
│   ├── main.py         App entry, middleware, route wiring
│   └── routes/         auth, mentor, planner, ncert, lecture,
│                       current_affairs, upload, pyq, evaluator,
│                       history, feedback, chat
├── agents/             Per-agent business logic + prompts
│   ├── mentor/         current_affairs/  evaluator/  lecture/
│   ├── ncert/          planner/          pyq/        upload/
├── graph/              LangGraph orchestration
│   ├── supervisor.py       Top-level router
│   ├── mentor_graph.py     Mentor subgraph (router→KB→web→generate)
│   ├── rag_graph.py        Reusable CRAG subgraph (all doc agents)
│   ├── agent_subgraphs.py  Planner / Evaluator / CA wrappers
│   ├── memory.py           Checkpointer + long-term store (Postgres)
│   ├── state.py            Shared AgentState contract
│   └── app_graph.py        Builds + compiles the whole graph
├── core/               Config, LLM router, vector store, DB, auth,
│                       embeddings, mentor KB, observability
├── models/             Pydantic request/response schemas
└── eval/               LLM evaluation harness + dataset
```

---

## 🛡️ Design Principles

1. **No hallucination.** Every prompt forbids inventing facts; volatile data is verified live or flagged.
2. **Graceful degradation.** Missing API keys or services fall back instead of crashing (Gemini→Groq, Postgres→SQLite, Qdrant→Chroma).
3. **Grounded answers.** Document agents answer *only* from the document; otherwise they say so.
4. **Background heavy work.** Slow steps (embeddings) run after the user already has their result.
5. **Observability built-in.** Every run is traceable end-to-end via Langfuse.

---

## 🗺️ Roadmap (high level)

- [ ] Local multilingual embeddings (remove embedding API quota) — after Oracle migration
- [ ] Self-hosted Qdrant on Oracle Always Free
- [ ] PYQ bank from past papers → searchable vector store
- [ ] Freemium: free demo tier + paid plan
- [ ] Chunked Whisper for long no-caption videos

---

*Built for UPSC aspirants. Notes are study aids — always cross-verify exam-critical facts (dates, cut-offs, vacancies) at the official source, upsc.gov.in.*
