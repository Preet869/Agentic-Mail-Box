import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

from config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EmailSession(Base):
    __tablename__ = "email_sessions"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    gmail_id: Mapped[str] = mapped_column(unique=True, index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(nullable=True)
    sender_email: Mapped[str]
    subject: Mapped[Optional[str]] = mapped_column(nullable=True)
    original_body: Mapped[str]
    agent_draft: Mapped[str]
    human_draft: Mapped[Optional[str]] = mapped_column(nullable=True)
    # pending_review | sent | discarded
    status: Mapped[str] = mapped_column(default="pending_review")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    actioned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # --- Stage 3: Agentic analysis fields ---
    priority_score: Mapped[Optional[int]] = mapped_column(nullable=True)       # 1–5
    priority_label: Mapped[Optional[str]] = mapped_column(nullable=True)       # Critical/High/Medium/Low/FYI
    detected_tone: Mapped[Optional[str]] = mapped_column(nullable=True)        # formal/casual/urgent/etc.
    identified_tasks: Mapped[Optional[str]] = mapped_column(nullable=True)     # JSON-encoded list[str]
    agent_draft_v1: Mapped[Optional[str]] = mapped_column(nullable=True)       # draft before self-correction
    self_critique: Mapped[Optional[str]] = mapped_column(nullable=True)        # JSON-encoded list[str] of issues found


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Inline migration: add Stage 3 columns to existing tables if they don't exist.
        # ALTER TABLE ADD COLUMN is idempotent via try/except on SQLite.
        new_columns = [
            "ALTER TABLE email_sessions ADD COLUMN priority_score INTEGER",
            "ALTER TABLE email_sessions ADD COLUMN priority_label TEXT",
            "ALTER TABLE email_sessions ADD COLUMN detected_tone TEXT",
            "ALTER TABLE email_sessions ADD COLUMN identified_tasks TEXT",
            "ALTER TABLE email_sessions ADD COLUMN agent_draft_v1 TEXT",
            "ALTER TABLE email_sessions ADD COLUMN self_critique TEXT",
        ]
        for stmt in new_columns:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists — safe to ignore


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# --- CRUD helpers ---

async def create_session(
    db: AsyncSession,
    *,
    gmail_id: str,
    sender_name: Optional[str],
    sender_email: str,
    subject: Optional[str],
    original_body: str,
    agent_draft: str,
    # Stage 3 fields (optional so Stage 1/2 code paths still work)
    priority_score: Optional[int] = None,
    priority_label: Optional[str] = None,
    detected_tone: Optional[str] = None,
    identified_tasks: Optional[list[str]] = None,
    agent_draft_v1: Optional[str] = None,
    self_critique: Optional[list[str]] = None,
) -> EmailSession:
    session = EmailSession(
        id=str(uuid.uuid4()),
        gmail_id=gmail_id,
        sender_name=sender_name,
        sender_email=sender_email,
        subject=subject,
        original_body=original_body,
        agent_draft=agent_draft,
        priority_score=priority_score,
        priority_label=priority_label,
        detected_tone=detected_tone,
        identified_tasks=json.dumps(identified_tasks) if identified_tasks is not None else None,
        agent_draft_v1=agent_draft_v1,
        self_critique=json.dumps(self_critique) if self_critique is not None else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_id(db: AsyncSession, session_id: str) -> Optional[EmailSession]:
    result = await db.execute(
        text("SELECT * FROM email_sessions WHERE id = :id"),
        {"id": session_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return await db.get(EmailSession, session_id)


async def get_session_by_gmail_id(db: AsyncSession, gmail_id: str) -> Optional[EmailSession]:
    result = await db.execute(
        text("SELECT id FROM email_sessions WHERE gmail_id = :gmail_id"),
        {"gmail_id": gmail_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return await db.get(EmailSession, row["id"])


async def list_sessions(db: AsyncSession) -> list[EmailSession]:
    result = await db.execute(
        text("SELECT id FROM email_sessions ORDER BY created_at DESC")
    )
    ids = [row["id"] for row in result.mappings().all()]
    sessions = []
    for sid in ids:
        s = await db.get(EmailSession, sid)
        if s:
            sessions.append(s)
    return sessions


async def update_human_draft(
    db: AsyncSession, session_id: str, human_draft: str
) -> Optional[EmailSession]:
    s = await db.get(EmailSession, session_id)
    if s is None:
        return None
    s.human_draft = human_draft
    await db.commit()
    await db.refresh(s)
    return s


async def mark_sent(db: AsyncSession, session_id: str) -> Optional[EmailSession]:
    s = await db.get(EmailSession, session_id)
    if s is None:
        return None
    s.status = "sent"
    s.actioned_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return s


async def mark_discarded(db: AsyncSession, session_id: str) -> Optional[EmailSession]:
    s = await db.get(EmailSession, session_id)
    if s is None:
        return None
    s.status = "discarded"
    s.actioned_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return s
