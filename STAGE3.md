# Stage 3 — Agentic AI with LangChain

## What Stage 3 Is

Stage 3 upgrades the email agent from a single-prompt reply generator into a genuine **agentic pipeline**. Instead of one Claude call that produces a draft, the agent now runs three distinct reasoning steps per email — each with a specific job — before presenting anything to the human reviewer.

The four capabilities added in this stage:

| Capability | What it means |
|------------|---------------|
| **Priority scoring** | The agent scores each email 1–5 for urgency and labels it (Critical, High, Medium, Low, FYI) |
| **Tone detection** | The agent identifies the emotional register of the incoming email (formal, urgent, casual, frustrated, friendly, neutral) |
| **Task identification** | The agent lists the specific action items the email requires |
| **Self-correction** | The agent writes a draft, then critiques its own work and revises before presenting it |

---

## The Agent Pipeline

Every email now passes through three sequential LangChain steps:

```
Incoming Email
      │
      ▼
┌─────────────────────────────────────────────────┐
│  Step 1: Analysis                               │
│  One LLM call → structured JSON output         │
│  → priority_score (1–5)                        │
│  → priority_label (Critical/High/Medium/Low)   │
│  → detected_tone (formal/urgent/casual/etc.)   │
│  → identified_tasks (list of action strings)   │
│  → summary (one sentence)                      │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 2: Draft Generation                       │
│  One LLM call → plain text output              │
│  Uses analysis context so the draft already    │
│  knows the tone and which tasks to address     │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 3: Self-Critique                          │
│  One LLM call → structured JSON output         │
│  Agent reviews its own draft for:              │
│  - Correct sender name                         │
│  - Tone match                                  │
│  - All tasks addressed                         │
│  - No hallucinated facts                       │
│  - Appropriate length                          │
│  → issues_found (list, empty if none)          │
│  → revised_draft (corrected, or unchanged)     │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
              AgentResult stored to DB
              Final draft shown in UI
```

Total: 3 LLM calls per email. All three run before the human sees anything. The human only ever sees the post-critique revised draft.

---

## Why LangChain

### Stage 1 and 2 used the raw Anthropic SDK directly

That was correct for those stages — single prompt in, single text out. The Anthropic SDK is the right tool for that.

### Stage 3 has a multi-step pipeline

Each step's output feeds the next. LangChain's LCEL (LangChain Expression Language) makes this clean:

```python
analysis_chain = analysis_prompt | llm | JsonOutputParser()
draft_chain    = draft_prompt    | llm | StrOutputParser()
critique_chain = critique_prompt | llm | JsonOutputParser()
```

The `|` pipe syntax chains a prompt template → the LLM → an output parser into a single callable. Each step is independently testable.

### Structured output parsing

The Analysis and Self-Critique steps need to return typed data (priority score, list of tasks, list of issues) — not free text. `JsonOutputParser` handles this automatically, retrying if the model returns malformed JSON.

### It stays compatible with the existing architecture

`langchain-anthropic` wraps the same Claude model we were already using. The Gmail client, FastAPI endpoints, SQLite database, and React frontend are all unchanged in their fundamental design.

---

## Priority System

| Score | Label | When assigned |
|-------|-------|---------------|
| 5 | Critical | Emergency language, legal matters, "urgent/ASAP", same-day deadline |
| 4 | High | Client-facing, decision awaited, deadline within a week |
| 3 | Medium | Standard business reply needed, no explicit deadline |
| 2 | Low | Informational, no clear action required |
| 1 | FYI | Notification-style, no reply expected |

The sidebar sorts pending emails by priority descending — Critical emails appear at the top automatically.

---

## Tone Detection

Possible values the agent assigns: `formal`, `casual`, `urgent`, `frustrated`, `friendly`, `neutral`.

The draft generation step receives the detected tone and mirrors it. A `frustrated` sender gets an empathetic, carefully worded reply. A `casual` sender gets a relaxed response. A `formal` business email gets a formal reply.

---

## Self-Correction: How It Works

After generating the first draft (`agent_draft_v1`), the agent runs a separate review call that checks five things:

1. Is the sender addressed by their correct first name?
2. Does the tone of the reply match the detected tone of the original email?
3. Does the reply address every task in `identified_tasks`?
4. Does the reply contain any invented facts or assumptions not in the original email?
5. Is the length appropriate?

If any check fails, the agent produces a `revised_draft` that fixes the issues. The list of `issues_found` is stored alongside both drafts.

**What you see in the UI:**
- The final (post-critique) draft is pre-loaded in the editable text area
- A collapsible "AI Reasoning" section appears at the bottom of the draft panel:
  - If issues were found and fixed: shows each issue with an amber dot
  - If no issues: shows "Agent was satisfied with the initial draft"
  - A "Revised" badge appears on the button when the draft was changed

---

## Database Changes

Six new columns were added to `email_sessions` via an inline migration in `init_db()`. The migration uses `ALTER TABLE ADD COLUMN` wrapped in try/except — safe to run on every startup, silently skipped if the column already exists. No Alembic, no migration files.

```sql
priority_score   INTEGER          -- 1–5
priority_label   TEXT             -- "Critical" | "High" | "Medium" | "Low" | "FYI"
detected_tone    TEXT             -- "formal" | "casual" | "urgent" | etc.
identified_tasks TEXT             -- JSON-encoded list of action strings
agent_draft_v1   TEXT             -- first draft before self-correction
self_critique    TEXT             -- JSON-encoded list of issues found
```

Existing rows from Stage 1 and Stage 2 have `NULL` in all six columns — they display correctly in the UI with no analysis panel shown.

---

## Files Changed in Stage 3

| File | What changed |
|------|-------------|
| `backend/requirements.txt` | Added `langchain`, `langchain-anthropic`, `langchain-core` |
| `backend/agent.py` | Full rewrite — 3-step LangChain pipeline replaces the single Claude call |
| `backend/database.py` | 6 new columns on `EmailSession`, inline migration, updated `create_session()` |
| `backend/models.py` | 6 new optional fields on `EmailSessionOut` |
| `backend/main.py` | Both `create_session()` calls updated to pass `AgentResult` fields |
| `frontend/src/api.ts` | 6 new optional fields on `EmailSession` TypeScript type |
| `frontend/src/components/EmailCard.tsx` | New "Agent Analysis" panel: priority badge, tone chip, task list |
| `frontend/src/components/DraftReview.tsx` | New collapsible "AI Reasoning" section with self-critique display |
| `frontend/src/components/SessionSidebar.tsx` | Priority badge per row, pending sessions sorted by priority descending |

---

## UI Changes

### EmailCard (left panel)

A new "Agent Analysis" strip appears between the email header and body when analysis data is present. It shows:

- A coloured priority badge (red = Critical, orange = High, amber = Medium, blue = Low, slate = FYI)
- A tone chip (e.g., "Urgent tone", "Formal tone")
- A bulleted list of action items the agent identified

### DraftReview (right panel)

A collapsible "AI Reasoning" button appears above the action buttons. Clicking it reveals:

- Whether the draft was revised after self-critique (amber "Revised" badge)
- The specific issues the agent found in its own first draft
- Or confirmation that no issues were found

### SessionSidebar

Each session row now shows a small coloured priority badge (e.g., "High" in orange) below the subject line. The pending sessions list is sorted highest priority first.

---

## Eval Data — Stage 3 Additions

Every email session now stores the full reasoning chain:

```
original email
→ analysis (priority + tone + tasks)
→ agent_draft_v1 (first attempt)
→ self_critique (what the agent found wrong)
→ agent_draft (final, post-critique version)
→ human_draft (what you changed it to, if anything)
→ status (sent / discarded)
```

This is a rich dataset for evaluating agent quality:
- Did the priority scoring match your judgement?
- Did the tone detection match the email?
- Did the self-critique catch real issues or imaginary ones?
- How much did the final draft differ from what you actually sent?

---

## Running Stage 3

No new setup steps. Restart the backend and the new pipeline activates automatically:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

The inline migration runs on startup and adds the new columns to your existing `mailbox.db`. All existing sessions are preserved.
