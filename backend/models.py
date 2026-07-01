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

    model_config = {"from_attributes": True}


class UpdateDraftRequest(BaseModel):
    human_draft: str


class FetchEmailResponse(BaseModel):
    session: EmailSessionOut
    message: str


class ApproveResponse(BaseModel):
    session: EmailSessionOut
    message: str


class DiscardResponse(BaseModel):
    session: EmailSessionOut
    message: str


class FetchBatchResponse(BaseModel):
    sessions: List[EmailSessionOut]
    fetched: int
    skipped: int
    message: str


class ErrorResponse(BaseModel):
    detail: str
