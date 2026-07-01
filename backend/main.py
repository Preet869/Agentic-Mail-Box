"""
FastAPI application for the Agentic Mail Box.

Endpoints:
  GET  /api/email/fetch          — Fetch one unread Gmail + generate Claude draft
  GET  /api/drafts               — List all stored sessions
  GET  /api/drafts/{id}          — Get one session
  PATCH /api/drafts/{id}         — Save human-edited draft text
  POST /api/drafts/{id}/approve  — Send via Gmail + mark sent
  DELETE /api/drafts/{id}        — Discard session
"""

import asyncio
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from agent import generate_draft_reply
from database import (
    init_db,
    get_db,
    create_session,
    get_session_by_id,
    get_session_by_gmail_id,
    list_sessions,
    update_human_draft,
    mark_sent,
    mark_discarded,
)
from gmail_client import get_one_unread_email, get_multiple_unread_emails, send_reply
from models import (
    EmailSessionOut,
    UpdateDraftRequest,
    FetchEmailResponse,
    FetchBatchResponse,
    ApproveResponse,
    DiscardResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Agentic Mail Box API",
    description="Human-in-the-loop email reply agent powered by Claude.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/email/fetch", response_model=FetchEmailResponse)
async def fetch_email(db: AsyncSession = Depends(get_db)):
    """
    Fetch the oldest unread Gmail message, run the Claude agent to generate
    a draft reply, persist the session, and return it for review.

    If the email was already fetched previously (same Gmail ID), return the
    existing session instead of creating a duplicate.
    """
    email = await asyncio.to_thread(get_one_unread_email)
    if email is None:
        raise HTTPException(status_code=404, detail="No unread emails found in inbox.")

    existing = await get_session_by_gmail_id(db, email.gmail_id)
    if existing:
        return FetchEmailResponse(
            session=EmailSessionOut.model_validate(existing),
            message="Email was already fetched — returning existing session.",
        )

    result = await asyncio.to_thread(generate_draft_reply, email)

    session = await create_session(
        db,
        gmail_id=email.gmail_id,
        sender_name=email.sender_name,
        sender_email=email.sender_email,
        subject=email.subject,
        original_body=email.body,
        agent_draft=result.final_draft,
        priority_score=result.priority_score,
        priority_label=result.priority_label,
        detected_tone=result.detected_tone,
        identified_tasks=result.identified_tasks,
        agent_draft_v1=result.agent_draft_v1,
        self_critique=result.self_critique,
    )

    return FetchEmailResponse(
        session=EmailSessionOut.model_validate(session),
        message="Email fetched and draft generated successfully.",
    )


@app.get("/api/emails/fetch-batch", response_model=FetchBatchResponse)
async def fetch_email_batch(
    max_results: int = 10, db: AsyncSession = Depends(get_db)
):
    """
    Fetch up to max_results unread emails from Gmail, generate Claude drafts
    for each new one concurrently, and return all sessions (new + existing).

    Emails already in the DB (matched by gmail_id) are skipped — no duplicate
    sessions and no wasted Claude calls.
    """
    emails = await asyncio.to_thread(get_multiple_unread_emails, max_results)
    if not emails:
        all_sessions = await list_sessions(db)
        return FetchBatchResponse(
            sessions=[EmailSessionOut.model_validate(s) for s in all_sessions],
            fetched=0,
            skipped=0,
            message="No new unread emails found in inbox.",
        )

    new_emails = []
    skipped = 0
    for email in emails:
        existing = await get_session_by_gmail_id(db, email.gmail_id)
        if existing:
            skipped += 1
        else:
            new_emails.append(email)

    # Generate all drafts concurrently (full 3-step pipeline per email)
    if new_emails:
        results = await asyncio.gather(
            *[asyncio.to_thread(generate_draft_reply, email) for email in new_emails]
        )
        for email, result in zip(new_emails, results):
            await create_session(
                db,
                gmail_id=email.gmail_id,
                sender_name=email.sender_name,
                sender_email=email.sender_email,
                subject=email.subject,
                original_body=email.body,
                agent_draft=result.final_draft,
                priority_score=result.priority_score,
                priority_label=result.priority_label,
                detected_tone=result.detected_tone,
                identified_tasks=result.identified_tasks,
                agent_draft_v1=result.agent_draft_v1,
                self_critique=result.self_critique,
            )

    all_sessions = await list_sessions(db)
    fetched = len(new_emails)
    return FetchBatchResponse(
        sessions=[EmailSessionOut.model_validate(s) for s in all_sessions],
        fetched=fetched,
        skipped=skipped,
        message=f"Fetched {fetched} new email(s), skipped {skipped} already processed.",
    )


@app.get("/api/drafts", response_model=List[EmailSessionOut])
async def list_drafts(db: AsyncSession = Depends(get_db)):
    sessions = await list_sessions(db)
    return [EmailSessionOut.model_validate(s) for s in sessions]


@app.get("/api/drafts/{session_id}", response_model=EmailSessionOut)
async def get_draft(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return EmailSessionOut.model_validate(session)


@app.patch("/api/drafts/{session_id}", response_model=EmailSessionOut)
async def update_draft(
    session_id: str,
    body: UpdateDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save the human-edited draft. Called automatically as the user types."""
    session = await update_human_draft(db, session_id, body.human_draft)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return EmailSessionOut.model_validate(session)


@app.post("/api/drafts/{session_id}/approve", response_model=ApproveResponse)
async def approve_draft(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Send the email via Gmail (using human_draft if edited, else agent_draft)
    then mark the session as sent.
    """
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.status != "pending_review":
        raise HTTPException(
            status_code=409,
            detail=f"Session is already '{session.status}' and cannot be sent again.",
        )

    body_to_send = session.human_draft or session.agent_draft

    await asyncio.to_thread(
        send_reply,
        to=session.sender_email,
        subject=session.subject or "",
        body=body_to_send,
        thread_id=session.gmail_id,
    )

    updated = await mark_sent(db, session_id)
    return ApproveResponse(
        session=EmailSessionOut.model_validate(updated),
        message="Email sent successfully.",
    )


@app.delete("/api/drafts/{session_id}", response_model=DiscardResponse)
async def discard_draft(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await mark_discarded(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return DiscardResponse(
        session=EmailSessionOut.model_validate(session),
        message="Draft discarded.",
    )
