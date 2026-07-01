"""
Gmail API client.

Handles OAuth 2.0 authentication and provides helpers for:
  - Fetching the single oldest unread email from the inbox
  - Sending a reply via the Gmail API

First-time setup: run `python gmail_client.py` to complete the browser OAuth flow.
This writes token.json next to this file, which is then reused on every subsequent run.
"""

import base64
import email as email_lib
import os
import re
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")


@dataclass
class ParsedEmail:
    gmail_id: str
    thread_id: str
    sender_name: Optional[str]
    sender_email: str
    subject: Optional[str]
    body: str


def _build_service():
    creds: Optional[Credentials] = None

    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GMAIL_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _parse_sender(from_header: str) -> tuple[Optional[str], str]:
    """Split 'Display Name <email@example.com>' into (name, email)."""
    match = re.match(r'^"?([^"<]+?)"?\s*<([^>]+)>$', from_header.strip())
    if match:
        name = match.group(1).strip() or None
        addr = match.group(2).strip()
        return name, addr
    return None, from_header.strip()


def _get_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _get_body(part)
            if text:
                return text

    return ""


def _strip_quoted_reply(body: str) -> str:
    """Remove quoted previous messages (lines starting with '>') from body."""
    lines = body.splitlines()
    clean = []
    for line in lines:
        if line.startswith(">"):
            break
        clean.append(line)
    return "\n".join(clean).strip()


def get_one_unread_email() -> Optional[ParsedEmail]:
    """
    Fetch the most recent unread email from the Primary inbox (last 7 days).
    Excludes promotions, social, updates, and forum emails.
    Returns None if there are no qualifying unread messages.
    """
    service = _build_service()

    query = (
        "is:unread "
        "in:inbox "
        "newer_than:7d "
        "-category:promotions "
        "-category:updates "
        "-category:social "
        "-category:forums"
    )

    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=1, q=query)
        .execute()
    )
    messages = results.get("messages", [])
    if not messages:
        return None

    msg_id = messages[0]["id"]
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )

    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    from_header = headers.get("From", "")
    subject = headers.get("Subject", "(no subject)")

    sender_name, sender_email = _parse_sender(from_header)
    body = _get_body(msg["payload"])
    body = _strip_quoted_reply(body)

    return ParsedEmail(
        gmail_id=msg_id,
        thread_id=msg["threadId"],
        sender_name=sender_name,
        sender_email=sender_email,
        subject=subject,
        body=body,
    )


def send_reply(
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: str,
    in_reply_to: Optional[str] = None,
) -> dict:
    """
    Send an email reply via Gmail.
    Returns the Gmail API response dict.
    """
    service = _build_service()

    mime_msg = MIMEText(body, "plain")
    mime_msg["To"] = to
    mime_msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if in_reply_to:
        mime_msg["In-Reply-To"] = in_reply_to
        mime_msg["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw, "threadId": thread_id})
        .execute()
    )
    return result


if __name__ == "__main__":
    # Run this script once to authenticate and write token.json
    print("Running Gmail OAuth flow...")
    _build_service()
    print("Authentication successful. token.json has been written.")
    email = get_one_unread_email()
    if email:
        print(f"\nFound unread email:")
        print(f"  From: {email.sender_name} <{email.sender_email}>")
        print(f"  Subject: {email.subject}")
        print(f"  Body preview: {email.body[:200]}...")
    else:
        print("\nNo unread emails found in inbox.")
