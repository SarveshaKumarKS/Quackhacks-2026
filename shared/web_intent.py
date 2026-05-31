"""
Pure helpers for the general web pipeline (no network) so they are unit-testable.

The orchestrator uses these to turn a goal into either a direct URL fetch or a
search query, and to build the prompt that summarizes extracted page text.
"""
import re
import urllib.parse
from typing import Optional

_URL_RE = re.compile(r'https?://[^\s)>\]]+')
_BARE_DOMAIN_RE = re.compile(r'^([\w-]+\.)+[a-z]{2,}(/\S*)?$', re.IGNORECASE)

DUCKDUCKGO_HTML = "https://duckduckgo.com/html/?q="


def extract_first_url(text: str) -> Optional[str]:
    """Return the first explicit http(s) URL in the text, or a bare domain token."""
    if not text:
        return None
    m = _URL_RE.search(text)
    if m:
        return m.group(0)
    for token in text.split():
        if _BARE_DOMAIN_RE.match(token):
            return token if token.startswith("http") else f"https://{token}"
    return None


def build_target(goal: str) -> str:
    """
    Resolve a goal to a navigable target: a direct URL if the goal contains one,
    otherwise a DuckDuckGo HTML search (scrape-friendly, no consent wall).
    """
    url = extract_first_url(goal)
    if url:
        return url
    return DUCKDUCKGO_HTML + urllib.parse.quote(goal)


def build_web_answer_prompt(goal: str, web_text: str, max_chars: int = 8000) -> str:
    """Prompt that asks the model to answer the goal using only extracted web content."""
    snippet = (web_text or "")[:max_chars]
    return (
        f'The user asked: "{goal}".\n\n'
        "Using ONLY the web content below, give a clear, helpful response — a summary, "
        "insights, or whatever the request implies. Use concise Markdown. If the content "
        "does not actually answer the request, say so plainly.\n\n"
        "WEB CONTENT:\n" + snippet
    )
