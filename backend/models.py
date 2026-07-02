from datetime import datetime
from typing import Optional, Literal, List

from pydantic import BaseModel


class EmailSessionOut(BaseModel):
    id: str
    gmail_id: str
    sender_name: Optional[str]
    sender_email: str
    subject: Optional[str]
    original_body: str
    agent_draft: str
    human_draft: Optional[str]
    status: Literal["pending_review", "sent", "discarded"]
    created_at: datetime
    actioned_at: Optional[datetime]

    # Stage 3 fields
    priority_score: Optional[int] = None
    priority_label: Optional[str] = None
    detected_tone: Optional[str] = None
    identified_tasks: Optional[str] = None   # JSON-encoded list[str]
    agent_draft_v1: Optional[str] = None
    self_critique: Optional[str] = None      # JSON-encoded list[str]

    # Stage 4 fields
    tools_used: Optional[str] = None         # JSON-encoded list[dict]

    model_config = {"from_attributes": True}


class UpdateDraftRequest(BaseModel):
    human_draft: str


class FetchEmailResponse(BaseModel):
    session: EmailSessionOut
    message: str


class FetchBatchResponse(BaseModel):
    sessions: List[EmailSessionOut]
    fetched: int
    skipped: int
    message: str


class ApproveResponse(BaseModel):
    session: EmailSessionOut
    message: str


class DiscardResponse(BaseModel):
    session: EmailSessionOut
    message: str


class ErrorResponse(BaseModel):
    detail: str
