"""
Stage 4 — LangChain agentic pipeline with tool use.

Four-step pipeline:
  1. Analysis      — priority, tone, tasks, summary (structured JSON)
  2. Tool Decision — agent decides which tools to call (if any) and calls them
  3. Draft         — generates reply using analysis + tool results as context
  4. Self-Critique — reviews its own draft, identifies issues, revises

Tools available to the agent:
  - get_current_date  — returns today's date (useful for relative date references)
  - check_holidays    — AbstractAPI: checks if a date is a public holiday
  - scrape_url        — AbstractAPI: reads content of a webpage from a URL in the email
"""

from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from gmail_client import ParsedEmail
from tools import ALL_TOOLS, TOOL_MAP


# ---------------------------------------------------------------------------
# LLM instances
# ---------------------------------------------------------------------------

_llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=1024,
)

# LLM with tools bound — used only for the tool-decision step
_llm_with_tools = _llm.bind_tools(ALL_TOOLS)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    priority_score: int
    priority_label: str
    detected_tone: str
    identified_tasks: list[str]
    summary: str
    tools_used: list[dict]        # [{"tool": name, "args": {...}, "result": "..."}]
    agent_draft_v1: str
    self_critique: list[str]
    final_draft: str


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
# Step 2: Tool decision and execution
# ---------------------------------------------------------------------------

_TOOL_DECISION_SYSTEM = """You are an email research assistant. Your job is to decide whether any 
tools are needed to gather information before drafting a reply to an email.

You have access to these tools:
- get_current_date: Call this if the email uses relative date references like "next Monday", 
  "this Friday", "tomorrow", "next week", or "in X days".
- check_holidays: Call this if the email mentions a specific calendar date for a meeting, 
  deadline, or event. You need to know if that date is a public holiday.
- scrape_url: Call this if the email contains a URL that the sender wants reviewed, 
  commented on, or referenced in the reply.

If none of the above apply, do NOT call any tools. Simply respond with the text: NO_TOOLS_NEEDED"""

def _run_tool_step(
    sender_display: str,
    subject: str,
    body: str,
    analysis: dict,
) -> tuple[str, list[dict]]:
    """
    Ask the agent whether it needs any tools, execute any tool calls it makes,
    and return (tool_context_str, tool_log).

    tool_context_str is injected into the draft prompt.
    tool_log is stored to the database.
    """
    tasks_str = ", ".join(analysis.get("identified_tasks", [])) or "reply appropriately"

    messages = [
        SystemMessage(content=_TOOL_DECISION_SYSTEM),
        HumanMessage(content=f"""Email to reply to:
From: {sender_display}
Subject: {subject}

{body}

--- Analysis ---
Priority: {analysis.get('priority_label')} ({analysis.get('priority_score')}/5)
Tone: {analysis.get('detected_tone')}
Tasks: {tasks_str}
Summary: {analysis.get('summary')}

Decide if any tools are needed and call them now."""),
    ]

    response = _llm_with_tools.invoke(messages)

    # No tool calls — agent decided none were needed
    if not response.tool_calls:
        return "", []

    tool_log: list[dict] = []
    tool_messages: list[ToolMessage] = []

    for tc in response.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_fn = TOOL_MAP.get(tool_name)

        if tool_fn is None:
            result_str = f"Unknown tool: {tool_name}"
        else:
            try:
                result_str = str(tool_fn.invoke(tool_args))
            except Exception as e:
                result_str = f"Tool error: {e}"

        tool_log.append({
            "tool": tool_name,
            "args": tool_args,
            "result": result_str,
        })
        tool_messages.append(
            ToolMessage(content=result_str, tool_call_id=tc["id"])
        )

    # Build a concise context string for the draft prompt
    context_lines = ["--- Research results from tools ---"]
    for entry in tool_log:
        context_lines.append(f"[{entry['tool']}] {entry['result']}")
    tool_context_str = "\n".join(context_lines)

    return tool_context_str, tool_log


# ---------------------------------------------------------------------------
# Step 3: Draft generation chain
# ---------------------------------------------------------------------------

_DRAFT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a professional email assistant writing a reply on behalf of the user.

Rules:
1. Address the sender by their first name if available, otherwise use a neutral greeting.
2. The email's tone is: {detected_tone} — match this tone in your reply.
3. You must address these specific tasks: {tasks_str}
4. If tool research results are provided below, use them naturally in your reply where relevant.
5. Respond only to what is explicitly stated. Do NOT invent facts.
6. Keep the reply concise and well-structured. Use short paragraphs.
7. End with a professional sign-off. Do NOT include a name — the user will add their signature.
8. Return ONLY the email body text. No subject line, no metadata, no commentary.

{tool_context}"""
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
# Step 4: Self-critique chain
# ---------------------------------------------------------------------------

_CRITIQUE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a strict email quality reviewer. Review a draft reply against the original email.

Check for these issues:
1. Does it correctly address the sender by their first name?
2. Does the tone match the original email's tone ({detected_tone})?
3. Does it address ALL tasks identified: {tasks_str}?
4. Does it contain any invented facts not in the original email or tool results?
5. If tool results were available, are they used appropriately (not ignored, not over-used)?
6. Is it appropriately concise?

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

{tool_context}

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
    Run the full 4-step pipeline for one email.
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

    # Step 2: Tool decision + execution
    tool_context_str, tool_log = _run_tool_step(
        sender_display=sender_display,
        subject=subject,
        body=email.body,
        analysis=analysis,
    )

    # Step 3: Generate draft (with optional tool context injected)
    draft_v1: str = _draft_chain.invoke({
        "sender_display": sender_display,
        "subject": subject,
        "body": email.body,
        "detected_tone": detected_tone,
        "tasks_str": tasks_str,
        "tool_context": tool_context_str,
    })
    draft_v1 = draft_v1.strip()

    # Step 4: Self-critique and revision
    critique_result: dict = _critique_chain.invoke({
        "sender_display": sender_display,
        "subject": subject,
        "body": email.body,
        "detected_tone": detected_tone,
        "tasks_str": tasks_str,
        "tool_context": tool_context_str,
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
        tools_used=tool_log,
        agent_draft_v1=draft_v1,
        self_critique=issues_found,
        final_draft=final_draft,
    )
