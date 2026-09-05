# Agentic Mailbox

An AI agent that reads unread emails, drafts context-aware replies, and queues them for human
approval — **it never sends anything without an explicit human click.** Built as a staged system,
starting from a single email and growing into a multi-step agent with tool use and self-critique.

> **Design principle throughout:** add the *minimum* intelligence the problem needs at each stage,
> prove it works, then layer on the next capability. Every stage below is framed as a decision —
> what I chose, what I rejected, and how it can fail.

---
## Architecture (at a glance)
```
User ─► React UI ─► FastAPI (async) ─► ┌─ Gmail API
                                       ├─ Claude API  (analyse → [tools] → draft → critique)
                                       └─ Database (SQLite → Postgres)
                                       ▼
                        Draft saved to DB ─► Human reviews in UI ─► "Approve & Send" ─► Gmail send
```

**The send path is unreachable without a human action.** The agent only ever *writes drafts*; the
`send` endpoint is triggered exclusively by an explicit approval click. This human-in-the-loop
guarantee is the core safety design, not an afterthought.

**Stack:** React · FastAPI + Uvicorn (ASGI server) · Claude API · Gmail API · SQLite→PostgreSQL ·
LangChain (Stage 3+) · SQLAlchemy ORM.

---

## Stage 1 — One email, end to end

**Goal:** prove the core loop on the smallest possible slice — pull a *single* unread email, generate
one draft, review it, send on approval. No batching, no agent logic yet.

**Why start this small:** I wanted to see how the model behaves on one email — does it get the sender
name right, the tone, the format? — before building anything around it. Getting the thin vertical
slice working end to end de-risks everything that comes later.

**Key decisions & tradeoffs:**
- **SQLite** — a file-based relational database, zero-config, ideal for a single user. *Rejected
  Postgres:* correct for scale, but overkill here; I noted the exact point it starts to hurt (concurrent
  writes — see Scaling).
- **FastAPI + Uvicorn** — FastAPI defines the async app so a request can await Claude/Gmail without
  blocking others; Uvicorn is the ASGI server that runs it and drives the event loop. *Rejected Flask*
  (no native async) and *Django* (async but heavy — ORM/admin/templating I don't need for an API).
- **Log everything from day one** — every session stores the original email, draft, critique, final
  draft, and whether the human edited before sending. This wasn't for Stage 1; it's so I'd have an
  **evaluation dataset** later without re-instrumenting.

**Success/failure definition (set before building):** success = correct sender name, tone, and format
on the draft. Failure signals = replies to the wrong emails, misread context, or wrong reply format.

---

## Stage 2 — From one email to a batch

**Goal:** handle up to 10 unread emails at once, with a three-column UI (inbox list → selected email →
draft) and per-email status (pending / sent / discarded).

**Key decision & tradeoff:**
- **Concurrent processing with `asyncio.gather()`** — generate all drafts in parallel (~5s) instead of
  sequentially (~50s). This is the payoff of the async choice in Stage 1. *Tradeoff:* concurrent calls
  raise burst load on the LLM/Gmail APIs, so rate-limit handling matters as volume grows.
- **Deduplicate by `gmail_id`** — skip emails already in the DB so re-syncing doesn't reprocess (and
  re-pay for) the same mail.

> **Honest note:** the parallelization approach here was something I worked through with an AI pair
> rather than designing alone. I've since made sure I understand *why* `asyncio.gather` gives the
> speedup (concurrent awaits on I/O-bound calls) rather than just that it does.

---

## Stage 3 — A reasoning pipeline (chain), not just a draft

**Goal:** replace the single draft call with a multi-step pipeline so each step reasons about the
email from a different angle.

**The pipeline:**
```
[1] Analyse  → priority score (1–5) + label, tone, task identified
[2] Draft    → uses Stage 1 findings to write the reply
[3] Critique → model reviews its own draft against a checklist:
               correct sender name · tone match · all tasks addressed ·
               no hallucinated facts · appropriate length → returns issues + revised draft
```

**What this actually is (precise framing):** this is a **chain** — a fixed sequence that runs the same
steps in the same order every time. It is *not yet* an agent; nothing here makes a runtime decision.
Splitting one big prompt into three focused steps trades **more cost/latency (3 calls)** for
**higher quality and per-step evaluability** — I can measure where the pipeline fails instead of
treating it as a black box.

- **Structured output (JSON)** at each step so downstream code can read `priority_score` as an integer
  rather than parsing a sentence. *Failure mode to handle:* malformed JSON — the parser needs a
  fallback/retry rather than crashing.
- **Self-critique / reflection** catches errors a single prompt misses (wrong name, missed question).
  *Open question I'd measure:* does the critique step earn its added cost, or does it sometimes revise
  a good draft into a worse one? I'd A/B with-vs-without critique on a labeled set to find out.

**Why LangChain here:** it's plumbing — it formats each step's prompt, enforces the output schema, and
parses the response into Python objects, so I'm not hand-writing that glue for every step. *It is not
RAG* — RAG is a retrieval pattern (fetch documents into context); this pipeline retrieves nothing, it
reasons in steps. (LangChain is a framework; RAG is a pattern — you could build RAG with or without
LangChain. They're not alternatives.)

---

## Stage 4 — One agentic decision: tool use

**Goal:** let the agent answer emails that need information it doesn't have — e.g. "what's next
Friday's date?" or a holiday/weather lookup — by *deciding at runtime* whether to call a tool.

**The pipeline becomes:**
```
Email → [1] Analyse → [2] Tool Decision → [3] Draft → [4] Critique → Final draft (for approval)
```

**What makes this agentic (precisely):** only step [2] is agentic — the model is given a menu of tools
and *decides* whether and which to call. The rest of the pipeline is still a chain. So the accurate
description is: **a chain with a single agentic decision point** — and that's deliberately the right
amount of agency for this problem. A full autonomous loop would add cost, latency, and failure surface
for no benefit here.

**How tool use works (the important mechanics):**
- The `@tool` decorator turns a Python function into something the model can "see" — it generates a
  schema from the function signature and, crucially, the **docstring**, which is the instruction the
  model reads to decide *when* to call it. Prompt engineering lives in that docstring.
- `bind_tools` attaches that tool menu to the API call.
- **The model never executes the tool** — it only says *"call `check_holidays` with `date=…`"*. My
  Python code makes the actual API request and feeds the result back. This separation is the whole
  security point: the model proposes, my code disposes.

**Failure modes I'd design for:** the model hallucinating a tool that doesn't exist, calling the wrong
tool, or passing bad arguments — each is caught by validating tool name/args against the registry and
returning a clean error to the model rather than crashing.

---

## Scaling (from single-user to ~10k users)

Three layers, each with the specific trigger that forces the change:

- **Storage — SQLite → PostgreSQL.** SQLite is file-based and serializes writes; two users hitting
  "Sync Inbox" at once causes a lock error. Postgres allows concurrent writes; add `user_id` to all
  tables, row-level security, and indexes on `gmail_id` and `status`. The **ORM (SQLAlchemy)** makes
  this ~one-line swap and also gives async SQLite (`aiosqlite`) in the meantime.
- **Processing — synchronous → task queue.** Right now the user waits while FastAPI calls Gmail, runs
  ~4 Claude calls per email, and writes the DB (30s+ for 10 emails). Move this to a background worker
  pool (**Celery + Redis**); the API returns immediately with "processing" and the client polls.
- **Horizontal scale.** Multiple Uvicorn workers behind a load balancer.

## Cost efficiency

- **Model routing** — cheap model (Haiku) for analysis/critique, stronger model only where it matters.
- **Prompt caching** — the analysis/critique system prompts are long and identical across calls; cache
  them for a large discount.
- **Result caching by email-body hash** — don't re-analyse an identical forwarded email twice.
- **Skip the tool step when unneeded** — pre-check in analysis (no dates/URLs in the body → no tool call).
- **Token budgeting** — for very long emails, a cheap summarisation pass before the expensive steps.

*(Fill in real numbers here — cost per email = 4 calls × tokens × price — a concrete figure makes every
optimization above far more convincing.)*

## Biggest production risk: data privacy

Every email body sent to Claude leaves the user's control. Mitigations: evaluate zero-data-retention
options, PII scrubbing before the LLM, a self-hosted model for highly sensitive mail, and rate limiting
so one account can't trigger thousands of LLM calls.

## Evaluation

The Stage-1 decision to log everything pays off here. Each session records the email, draft v1, the
critique, the final draft, and whether the human edited before approving — a ready-made eval dataset.
Signals to track: how often humans significantly edit drafts, discard rate, and which priority labels
correlate with discards. *(Next step: hand-label a ground-truth set for priority/tone so I'm measuring
against truth, not just human-edit proxies.)*
