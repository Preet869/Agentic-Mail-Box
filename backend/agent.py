"""
Stage 3 — LangChain agentic pipeline for email draft generation.

Three-step chain:
  1. Analysis   — priority score, tone, tasks, summary (structured JSON output)
  2. Draft      — generates reply using analysis context
  3. Self-Critique — reviews its own draft, identifies issues, produces revised draft

The full result is stored in the database so every field is available for
evaluation and future prompt improvement.
"""

from dataclasses import dataclass
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from gmail_client import ParsedEmail


# ---------------------------------------------------------------------------
# LLM instance (shared across all chain steps)
# ---------------------------------------------------------------------------

_llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=1024,
)


# ---------------------------------------------------------------------------
# Result dataclass returned to the caller
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    priority_score: int          # 1–5 (5 = most urgent)
    priority_label: str          # "Critical" | "High" | "Medium" | "Low" | "FYI"
    detected_tone: str           # "formal" | "casual" | "urgent" | "frustrated" | "friendly" | "neutral"
    identified_tasks: list[str]  # ["Confirm meeting", "Provide update"]
    summary: str                 # one-sentence summary of what the email is about
    agent_draft_v1: str          # draft before self-correction
    self_critique: list[str]     # issues the agent found in its own draft
    final_draft: str             # revised draft (may be same as v1 if no issues)


# ---------------------------------------------------------------------------
# Step 1: Analysis chain
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert email analyst. Given an incoming email, return a JSON object with these exact fields:

{{
  "priority_score": <integer 1-5 where 5=Critical, 4=High, 3=Medium, 2=Low, 1=FYI>,
  "priority_label": <"Critical" | "High" | "Medium" | "Low" | "FYI">,
  "detected_tone": <"formal" | "casual" | "urgent" | "frustrated" | "friendly" | "neutral">,
  "identified_tasks": [<list of specific action strings required to respond>],
  "summary": <one sentence describing what this email is about and what response is needed>
}}

Priority scoring guide:
- 5 Critical: emergency, legal, "urgent", "ASAP", deadline today
- 4 High: deadline within a week, awaiting your decision, client-facing
- 3 Medium: standard reply needed, no explicit deadline
- 2 Low: informational, no clear action required
- 1 FYI: notification-style, no reply expected

Return ONLY valid JSON. No commentary, no markdown code blocks."""
    ),
    (
        "human",
        """Analyse this email:

From: {sender_display}
Subject: {subject}

{body}"""
    ),
])

_analysis_chain = _ANALYSIS_PROMPT | _llm | JsonOutputParser()


# ---------------------------------------------------------------------------
# Step 2: Draft generation chain
# ---------------------------------------------------------------------------

_DRAFT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a professional email assistant writing a reply on behalf of the user.

Rules:
1. Address the sender by their first name if available, otherwise use a neutral greeting.
2. The email's tone is: {detected_tone} — match this tone in your reply.
3. You must address these specific tasks: {tasks_str}
4. Respond only to what is explicitly stated. Do NOT invent facts or assumptions.
5. Keep the reply concise and well-structured. Use short paragraphs.
6. End with a professional sign-off. Do NOT include a name — the user will add their signature.
7. Return ONLY the email body text. No subject line, no metadata, no commentary."""
    ),
    (
        "human",
        """Write a draft reply to this email:

From: {sender_display}
Subject: {subject}

{body}

Write the reply body now:"""
    ),
])

_draft_chain = _DRAFT_PROMPT | _llm | StrOutputParser()


# ---------------------------------------------------------------------------
# Step 3: Self-critique chain
# ---------------------------------------------------------------------------

_CRITIQUE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a strict email quality reviewer. Review a draft reply against the original email.

Check for these issues:
1. Does it correctly address the sender by their first name?
2. Does the tone match the original email's tone ({detected_tone})?
3. Does it address ALL tasks identified: {tasks_str}?
4. Does it contain any invented facts or assumptions not in the original email?
5. Is it appropriately concise (not too long, not too short)?

Return a JSON object with these exact fields:
{{
  "issues_found": [<list of specific issue strings, empty list if none>],
  "revised_draft": <the corrected draft — if no issues, return the original draft unchanged>
}}

Return ONLY valid JSON. No commentary, no markdown code blocks."""
    ),
    (
        "human",
        """Original email:
From: {sender_display}
Subject: {subject}

{body}

---
Draft reply to review:

{draft_v1}

Review the draft and return your JSON response:"""
    ),
])

_critique_chain = _CRITIQUE_PROMPT | _llm | JsonOutputParser()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_draft_reply(email: ParsedEmail) -> AgentResult:
    """
    Run the full 3-step LangChain pipeline for one email.
    Returns an AgentResult with all fields populated.
    """
    sender_display = (
        f"{email.sender_name} ({email.sender_email})"
        if email.sender_name
        else email.sender_email
    )
    subject = email.subject or "(no subject)"

    # Step 1: Analyse
    analysis: dict = _analysis_chain.invoke({
        "sender_display": sender_display,
        "subject": subject,
        "body": email.body,
    })

    priority_score = int(analysis.get("priority_score", 3))
    priority_label = analysis.get("priority_label", "Medium")
    detected_tone = analysis.get("detected_tone", "neutral")
    identified_tasks: list[str] = analysis.get("identified_tasks", [])
    summary = analysis.get("summary", "")
    tasks_str = ", ".join(identified_tasks) if identified_tasks else "reply appropriately"

    # Step 2: Generate draft
    draft_v1: str = _draft_chain.invoke({
        "sender_display": sender_display,
        "subject": subject,
        "body": email.body,
        "detected_tone": detected_tone,
        "tasks_str": tasks_str,
    })
    draft_v1 = draft_v1.strip()

    # Step 3: Self-critique and revision
    critique_result: dict = _critique_chain.invoke({
        "sender_display": sender_display,
        "subject": subject,
        "body": email.body,
        "detected_tone": detected_tone,
        "tasks_str": tasks_str,
        "draft_v1": draft_v1,
    })

    issues_found: list[str] = critique_result.get("issues_found", [])
    final_draft: str = critique_result.get("revised_draft", draft_v1).strip()

    return AgentResult(
        priority_score=priority_score,
        priority_label=priority_label,
        detected_tone=detected_tone,
        identified_tasks=identified_tasks,
        summary=summary,
        agent_draft_v1=draft_v1,
        self_critique=issues_found,
        final_draft=final_draft,
    )
