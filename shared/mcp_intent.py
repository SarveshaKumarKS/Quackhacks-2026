"""
Pure helpers for MCP task handling (no network, no heavy imports) so they can be
unit-tested in isolation. The orchestrator combines these with Gemini + mcp_google.

Covers:
  - confirm-before-send detection (is_negative / is_affirmative)
  - prompt construction for email drafting and doc content
  - human-readable calendar formatting
"""
import re
from typing import List, Dict, Any

_AFFIRMATIVE = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed",
    "approved", "send", "go", "do", "lgtm", "perfect", "great",
}
_AFFIRMATIVE_PHRASES = (
    "send it", "go ahead", "do it", "please do", "sounds good", "looks good",
    "ship it", "that works", "send the email",
)

_NEGATIVE = {"no", "nope", "cancel", "stop", "abort", "discard", "nevermind"}
_NEGATIVE_PHRASES = (
    "never mind", "don't send", "do not send", "dont send", "not now",
    "hold off", "don't", "do not",
)

_CONFIRMATION_ONLY_PHRASES = _AFFIRMATIVE_PHRASES + _NEGATIVE_PHRASES


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _words(text: str) -> set:
    return set(re.findall(r"[a-z']+", text))


def is_negative(text: str) -> bool:
    """True if the reply clearly cancels/declines the action."""
    t = _norm(text)
    if not t:
        return False
    if any(p in t for p in _NEGATIVE_PHRASES):
        return True
    return bool(_words(t) & _NEGATIVE)


def is_affirmative(text: str) -> bool:
    """
    True if the reply clearly approves the action. Negation guards first so that
    'don't send' / 'do not send' are NOT misread as approval (they contain 'send').
    Callers should still check is_negative() before is_affirmative().
    """
    t = _norm(text)
    if not t:
        return False
    if any(p in t for p in _NEGATIVE_PHRASES):
        return False
    if any(p in t for p in _AFFIRMATIVE_PHRASES):
        return True
    return bool(_words(t) & _AFFIRMATIVE)


def is_standalone_confirmation(text: str) -> bool:
    """
    True for short approval/cancel replies that only make sense when there is an
    active pending prompt. These should be ignored while idle/completed so a stale
    "yes" cannot become a brand-new desktop task.
    """
    t = _norm(text)
    if not t:
        return False
    if t in _CONFIRMATION_ONLY_PHRASES:
        return True
    words = _words(t)
    if not words:
        return False
    if len(words) <= 3 and (words <= _AFFIRMATIVE or words <= _NEGATIVE):
        return True
    return False


def build_email_draft_prompt(goal: str, recipient_hint: str = "", revision: str = "",
                             memory_context: str = "") -> str:
    """Instruction text for Gemini to produce a {to, subject, body} email draft."""
    parts = [
        "You are drafting an email on behalf of the user. Write a professional, concise email.",
        f"User request: {goal}",
    ]
    if memory_context:
        parts.append(memory_context)
    if recipient_hint:
        parts.append(
            f"Intended recipient (use as 'to' if it is an email address, otherwise infer): {recipient_hint}"
        )
    if revision:
        parts.append(f"Revise the previous draft according to this instruction: {revision}")
    parts.append("Return the recipient email address, a subject line, and the body.")
    return "\n".join(parts)


def build_doc_content_prompt(goal: str) -> str:
    """Instruction text for Gemini to produce Markdown content to append to a Doc."""
    return (
        "Write clean, well-structured Markdown content that fulfills this request, "
        "suitable to append to a Google Doc. Do not include any preamble or meta commentary.\n\n"
        f"Request: {goal}"
    )


def format_calendar_events(events: List[Dict[str, Any]]) -> str:
    """Human-readable summary of calendar events for logs / nudges."""
    if not events:
        return "No upcoming events found."
    lines = ["Upcoming events:"]
    for e in events:
        lines.append(f"• {e.get('start', '?')} — {e.get('title', '(no title)')}")
    return "\n".join(lines)
