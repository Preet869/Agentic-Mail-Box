"""
Claude agent for generating email draft replies.

Given a parsed incoming email, produces a draft reply that:
  - Addresses the sender by their first name
  - Matches the tone of the original (formal vs. casual)
  - Responds only to what's in the email — no hallucinated facts
  - Is concise and clear
"""

import anthropic

from config import settings
from gmail_client import ParsedEmail

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are a professional email assistant. Your job is to write a draft reply to an incoming email on behalf of the user.

Rules you must follow:
1. Address the sender by their first name if available, otherwise use a neutral greeting.
2. Mirror the tone of the original email — if it is formal, reply formally; if casual, reply in kind.
3. Respond only to what is explicitly stated in the email. Do NOT invent facts, make assumptions about the sender's business, or add information that wasn't provided.
4. Keep the reply concise and well-structured. Use short paragraphs.
5. End with a professional sign-off. Do NOT include a name at the end — the user will add their own signature.
6. Return ONLY the email body text. Do not include a subject line, metadata, or any commentary about the draft.
"""


def generate_draft_reply(email: ParsedEmail) -> str:
    """
    Call Claude to generate a draft reply for the given email.
    Returns the raw reply text.
    """
    sender_display = (
        f"{email.sender_name} ({email.sender_email})"
        if email.sender_name
        else email.sender_email
    )

    user_message = f"""\
Please write a draft reply to the following email.

--- INCOMING EMAIL ---
From: {sender_display}
Subject: {email.subject or "(no subject)"}

{email.body}
--- END EMAIL ---

Write the reply body now:"""

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()
