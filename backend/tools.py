"""
Stage 4 — LangChain tools the agent can call autonomously.

Three tools:
  1. get_current_date   — returns today's date (no API, always available)
  2. check_holidays     — AbstractAPI Holidays: checks if a date is a public holiday
  3. scrape_url         — AbstractAPI Scrape: reads the content of a webpage

The agent decides which tools to invoke based on the email content.
No tool is called unless the agent judges it relevant.
"""

import re
import httpx
from datetime import date as date_type

from langchain_core.tools import tool

from config import settings


# ---------------------------------------------------------------------------
# Tool 1: Current date (no API needed)
# ---------------------------------------------------------------------------

@tool
def get_current_date() -> str:
    """
    Returns today's date in YYYY-MM-DD format.
    Call this when the email uses relative date references like
    'next Monday', 'this Friday', 'in two weeks', or 'tomorrow'.
    """
    today = date_type.today()
    return f"Today is {today.strftime('%A, %B %d, %Y')} ({today.isoformat()})"


# ---------------------------------------------------------------------------
# Tool 2: Holiday checker (AbstractAPI Holidays)
# ---------------------------------------------------------------------------

@tool
def check_holidays(date: str, country_code: str = "") -> str:
    """
    Check whether a specific date is a public holiday.
    Call this when the email mentions a specific date for a meeting, deadline,
    or event, so you can flag public holidays in the reply.

    Args:
        date: The date to check in YYYY-MM-DD format (e.g. '2026-07-04')
        country_code: ISO 3166-1 alpha-2 country code (e.g. 'AU', 'US', 'GB').
                      Leave empty to use the default country.
    """
    if not settings.Calendar:
        return "Holiday API key not configured — cannot check holidays."

    country = country_code.strip().upper() or settings.DEFAULT_COUNTRY_CODE

    try:
        parsed = date_type.fromisoformat(date.strip())
    except ValueError:
        return f"Could not parse date '{date}'. Please provide a date in YYYY-MM-DD format."

    try:
        response = httpx.get(
            "https://holidays.abstractapi.com/v1/",
            params={
                "api_key": settings.Calendar,
                "country": country,
                "year": parsed.year,
                "month": parsed.month,
                "day": parsed.day,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        holidays: list = response.json()
    except Exception as e:
        return f"Holiday API error: {e}"

    date_display = parsed.strftime("%B %d, %Y")
    if not holidays:
        return f"{date_display} is not a public holiday in {country}."

    names = [h.get("name", "Unknown holiday") for h in holidays]
    holiday_list = ", ".join(names)
    return f"{date_display} is a public holiday in {country}: {holiday_list}."


# ---------------------------------------------------------------------------
# Tool 3: Web scraper (AbstractAPI Scrape)
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@tool
def scrape_url(url: str) -> str:
    """
    Fetch and return a plain-text summary of a webpage's content.
    Call this when the email contains a URL that the sender wants you to
    look at, review, or reference in your reply.

    Args:
        url: The full URL to scrape (e.g. 'https://example.com/product')
    """
    if not settings.Scrape:
        return "Scrape API key not configured — cannot fetch URL."

    try:
        response = httpx.get(
            "https://scrape.abstractapi.com/v1/",
            params={
                "api_key": settings.Scrape,
                "url": url,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"Scrape API error for {url}: {e}"

    body_html: str = data.get("body", "") or ""
    plain_text = _strip_html(body_html)

    # Limit to 1500 characters so it fits cleanly in the prompt context
    if len(plain_text) > 1500:
        plain_text = plain_text[:1500] + "… [content truncated]"

    if not plain_text:
        return f"Could not extract readable content from {url}."

    return f"Content from {url}:\n{plain_text}"


# ---------------------------------------------------------------------------
# Tool registry — used by agent.py
# ---------------------------------------------------------------------------

ALL_TOOLS = [get_current_date, check_holidays, scrape_url]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
