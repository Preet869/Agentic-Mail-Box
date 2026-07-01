# Tech Stack — Agentic Mail Box

## Why This Stack Fits This Application

The Agentic Mail Box has three non-negotiable requirements that drove every technology decision:

1. **External API calls are slow and async** — Gmail reads, Claude generations, and Gmail sends all involve network I/O that can take 2–10 seconds each. The backend must handle them without blocking.
2. **Human is always in the loop** — the send path must be gated behind an explicit user action. The stack must make it structurally easy to enforce this (no background jobs that silently send).
3. **Stage 1 is intentionally minimal** — evaluating one email at a time means we don't need distributed queues, caches, or a heavy database. The stack should be learnable and replaceable as requirements grow.

---

## Chosen Stack

### Backend — Python + FastAPI + Uvicorn

**What it is:** FastAPI is a modern, async-native Python web framework. Uvicorn is the ASGI server that runs it.

**Why it's the right fit:**

- **Async-first by design.** `async def` route handlers and `await` let the server handle Gmail and Claude API calls without blocking threads. A single Uvicorn worker can handle multiple in-flight requests while waiting on external I/O.
- **Python is the lingua franca of AI tooling.** The Anthropic Python SDK, Google API client, and LangChain all target Python first. Switching languages would mean lagging behind the ecosystem.
- **Automatic API docs.** FastAPI generates interactive OpenAPI docs at `/docs` out of the box — essential for testing the agent's output against real emails during Stage 1 evaluation without touching the frontend.
- **Pydantic integration.** Request/response validation is built in. The `EmailSessionOut` schema ensures the frontend always receives a predictable, typed shape regardless of what's in the database.
- **Low ceremony.** A complete working endpoint is 5 lines. That matches the pace of Stage 1 — validate quickly, iterate fast.

**Alternatives considered:**

| Option | Why not chosen |
|--------|---------------|
| **Django + DRF** | Much heavier — ORM, admin, migrations, settings all bundled in. Significant boilerplate for what is essentially 6 endpoints. Async support exists but feels bolted on. |
| **Node.js + Express** | Would force a context-switch away from Python's AI library ecosystem. The Anthropic JS SDK is secondary to the Python SDK in terms of documentation and examples. |
| **Node.js + Fastify** | Same ecosystem problem as Express. Also means splitting the codebase language across frontend (TS) and backend (also TS), which looks appealing but loses the Python AI tooling advantage. |
| **Flask** | Synchronous by default — requires `asyncio` workarounds for concurrent Gmail + Claude calls. Older ecosystem around AI integrations. |

---

### AI Model — Claude (Anthropic) via the `anthropic` SDK

**What it is:** Claude is Anthropic's large language model family. The `claude-opus-4-5` model is used for draft generation via a single API call.

**Why it's the right fit:**

- **Instruction following.** Claude is particularly strong at following negative constraints ("do not hallucinate", "do not add information not in the email"). For an email agent, following constraints matters more than raw capability.
- **Long context window.** Email threads can be long. Claude handles large payloads without degradation in reply quality.
- **Official Python SDK.** `anthropic` is a first-party, actively maintained package with async support. The system prompt / user message pattern maps cleanly to email context.
- **Safety alignment.** Anthropic's Constitutional AI training means Claude is less likely to generate inappropriate email content — relevant when the output is going to real people.

**Alternatives considered:**

| Option | Why not chosen |
|--------|---------------|
| **OpenAI GPT-4o** | Also excellent. The primary reason for Claude is alignment and instruction-following characteristics. OpenAI is a straightforward swap if preferred — the agent is abstracted behind `agent.py`. |
| **Google Gemini** | Good long-context model, but since we're already calling Google's Gmail API, mixing two Google services creates entangled auth complexity. Also less established for agentic email tasks. |
| **Local model (Ollama / LLaMA 3)** | Eliminates API cost and keeps email data on-device — a real privacy advantage. However, quality for nuanced tone-matching in email replies is significantly below frontier models for Stage 1 evaluation. A local model swap is possible in Stage 2. |
| **LangChain agent** | LangChain adds an abstraction layer (chains, tools, memory) useful for multi-step agents. Our use case is a single prompt-response cycle — LangChain would add complexity with no benefit at this stage. |

---

### Gmail Integration — `google-api-python-client` + `google-auth-oauthlib`

**What it is:** Google's official Python client libraries for the Gmail REST API, with OAuth 2.0 authentication.

**Why it's the right fit:**

- **Official, maintained, and stable.** Google owns this library — breaking changes are versioned and signalled well in advance.
- **Fine-grained OAuth scopes.** We request only `gmail.readonly`, `gmail.send`, and `gmail.compose`. The user can see exactly what the application has access to in their Google account settings and can revoke it independently.
- **Thread-aware.** The library gives direct access to `threadId`, which is needed to send replies that appear correctly in the same conversation thread — not as a new email.
- **Desktop app OAuth flow.** For Stage 1 (single user, no multi-tenancy), the `InstalledAppFlow` that opens a browser tab is the correct Google-approved flow. No server-side redirect URI needed.

**Alternatives considered:**

| Option | Why not chosen |
|--------|---------------|
| **IMAP/SMTP (imaplib / smtplib)** | Protocol-level access. Works but requires enabling "Less secure apps" or App Passwords, which Google is deprecating. No thread IDs, no label access, inconsistent cross-provider behaviour. |
| **Gmail API via `httpx` directly** | Possible but means hand-writing auth refresh logic, token storage, and all API serialisation. The official client handles all of this. |
| **Nylas API** | A unified email abstraction layer (Gmail, Outlook, iCloud in one SDK). Good for multi-provider Stage 2, but adds a paid third-party dependency and an extra network hop for Stage 1. |
| **Microsoft Graph API (Outlook)** | Different provider entirely. Could be added in Stage 2 alongside Gmail. |

---

### Database — SQLite + SQLAlchemy (async) + aiosqlite

**What it is:** SQLite is a file-based relational database. SQLAlchemy is a Python ORM with async support. `aiosqlite` is an async driver for SQLite.

**Why it's the right fit:**

- **Zero infrastructure.** No database server to install, configure, or run. The database is a single file (`mailbox.db`) — perfect for Stage 1 where the goal is evaluation, not scale.
- **Async-compatible.** The `aiosqlite` + SQLAlchemy async combination means database queries don't block the FastAPI event loop, consistent with the rest of the stack.
- **The eval dataset lives on disk.** Every `(original email, agent draft, human action)` triple is persisted automatically. That file is the Stage 2 training/evaluation dataset. SQLite can be opened directly in tools like DB Browser or queried with `pandas`.
- **SQLAlchemy ORM means easy migration.** The `EmailSession` model and CRUD functions in `database.py` are database-agnostic. Switching to PostgreSQL in Stage 2 requires changing one line in `.env` (`DATABASE_URL`) and installing `asyncpg`. No application code changes.

**Alternatives considered:**

| Option | Why not chosen |
|--------|---------------|
| **PostgreSQL (Supabase)** | The right choice for Stage 2 — concurrent users, row-level security, real-time subscriptions. Overkill for evaluating a single email. Added infrastructure dependency with no benefit at this scale. |
| **MongoDB** | Document store is a natural fit for email JSON payloads, but introduces a non-relational query model that complicates the eval data analysis (SQL queries on approval logs are more ergonomic than Mongo aggregation pipelines). |
| **Raw SQLite (no ORM)** | Simpler short-term but requires hand-writing SQL strings. SQLAlchemy's typed models give IDE autocomplete and make the Postgres migration one-line. |
| **Redis** | In-memory store — wrong persistence model. Data loss on restart would lose eval data. |

---

### Frontend — React + TypeScript + Vite + Tailwind CSS

**What it is:** React 18 for UI components, TypeScript for type safety, Vite as the dev/build tool, Tailwind CSS for styling.

**Why it's the right fit:**

- **React is the right scope.** The UI is a single page with two panels (original email + editable draft) and three states (empty, reviewing, actioned). React's component model matches this exactly without over-engineering.
- **TypeScript catches the API contract at compile time.** The `EmailSession` interface in `api.ts` mirrors the Pydantic model in `models.py`. If the backend schema changes, TypeScript errors surface immediately — before you even run the app.
- **Vite's dev server proxy.** The `vite.config.ts` proxy forwards `/api/*` to `localhost:8000`. This means the frontend code never contains hardcoded backend URLs and CORS is a non-issue in development.
- **Tailwind removes the UI decision overhead.** For a Stage 1 tool, Tailwind's utility classes produce clean, maintainable UI without choosing a component library. The design can be refined without restructuring CSS files.
- **No client-side routing needed.** The app has one view. Adding React Router for a single route would be unnecessary complexity.

**Alternatives considered:**

| Option | Why not chosen |
|--------|---------------|
| **Next.js** | Brings SSR, file-based routing, and API routes. All useful for Stage 2 (public-facing product, SEO, auth). For a local evaluation tool with a separate FastAPI backend, Next.js adds build complexity and opinionated routing with zero benefit. |
| **Vue 3** | Equally capable. React was chosen because the ecosystem around React (especially for AI-adjacent tooling dashboards) is larger and the team is more likely already familiar. |
| **Svelte / SvelteKit** | Excellent DX and smaller bundle. Less mature ecosystem for the kinds of data-heavy evaluation UIs that Stage 2 may need. |
| **Plain HTML + Vanilla JS** | Works for Stage 1 but doesn't scale. Adding eval metrics, history views, or annotation tools in Stage 2 would require reinventing the component model. |
| **shadcn/ui or MUI** | Component libraries trade customisation for consistency. For two components (`EmailCard`, `DraftReview`), the overhead of learning a component library's API isn't worth it. Tailwind gives full control. |

---

## Migration Path to Stage 2

The stack was chosen so that scaling up requires adding, not rewriting:

| Stage 1 (now) | Stage 2 upgrade path |
|---------------|----------------------|
| SQLite (`mailbox.db`) | Change `DATABASE_URL` to `postgresql+asyncpg://...` — zero ORM code changes |
| Single Gmail account (Desktop OAuth) | Web OAuth flow + multi-user token storage |
| One email at a time (manual trigger) | Background polling with `asyncio` task or Celery worker |
| Claude via single prompt | Swap `agent.py` for LangChain agent with memory and tool use |
| Local React dev server | Deploy React build as static assets behind FastAPI or on Vercel |
| SQLite eval logs | Export to Supabase / BigQuery for annotation and fine-tuning |
