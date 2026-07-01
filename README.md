# Agentic Mail Box

An agentic email assistant that reads your Gmail inbox, generates draft replies using Claude, and lets you review, edit, and approve before anything is sent. **No email is ever sent without explicit human approval.**

## Architecture

```
Gmail API → FastAPI Backend → Claude (Anthropic) → SQLite DB
                                                        ↕
                                               React Frontend
                                         (Review · Edit · Approve)
```

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── gmail_client.py      # Gmail OAuth + read/send helpers
│   ├── agent.py             # Claude prompt + draft generation
│   ├── database.py          # SQLite schema + async CRUD
│   ├── models.py            # Pydantic request/response schemas
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   └── components/
│   │       ├── EmailCard.tsx
│   │       └── DraftReview.tsx
│   └── package.json
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Google account with Gmail
- An Anthropic API key

---

## Setup

### 1. Gmail API credentials (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. Create OAuth 2.0 credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file and rename it `credentials.json`
5. Place `credentials.json` in the `backend/` folder

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in your ANTHROPIC_API_KEY
```

**First-time Gmail authentication** (opens a browser window):

```bash
python gmail_client.py
```

This writes `token.json` to `backend/` and is only needed once. The token auto-refreshes after that.

### 3. Run the backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Usage (Stage 1)

1. Open http://localhost:5173
2. Click **"Fetch Email"** — the agent reads your oldest unread Gmail and generates a draft reply
3. Review the original email on the left and the AI-generated draft on the right
4. Edit the draft directly in the text area if needed
5. Click **"Approve & Send"** to send, or **"Discard"** to delete the draft

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/email/fetch` | Fetch one unread email + generate draft |
| `GET` | `/api/drafts` | List all sessions |
| `GET` | `/api/drafts/{id}` | Get one session |
| `PATCH` | `/api/drafts/{id}` | Update human-edited draft |
| `POST` | `/api/drafts/{id}/approve` | Send via Gmail + mark sent |
| `DELETE` | `/api/drafts/{id}` | Discard session |

---

## Evaluation (Stage 2 prep)

Every session in `mailbox.db` records the full triple:

```
original email → agent draft → human action (edited draft + approve, or discard)
```

This dataset can be used to evaluate agent quality: did it get the name right, was the tone correct, did it address all points?
