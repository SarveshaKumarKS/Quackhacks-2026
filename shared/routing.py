"""
Single source of truth for execution routing (see ROUTING.md).

The orchestrator must NOT keep its own ad-hoc keyword lists. It calls
`classify_goal()` to get exactly one route, following the decision ladder:

    1. Can an MCP/API do this?   -> "mcp"      (Docs / Sheets / Gmail / Calendar)
    2. Else, is it a web task?   -> "browser"  (headless Chrome over CDP)
    3. Else (native desktop)?    -> "desktop"  (PyAutoGUI, foreground only)

MCP always wins over browser/desktop (locked decision). Only "desktop" requires
Profile B to be the foreground console; "mcp" and "browser" are profile-independent.
"""
import re
from typing import Literal, Optional, NamedTuple

Route = Literal["mcp", "browser", "desktop"]
MCPCapability = Literal["gmail", "calendar", "docs", "sheets"]


class RoutingDecision(NamedTuple):
    route: Route
    mcp_capability: Optional[MCPCapability]  # set only when route == "mcp"
    reason: str

    @property
    def needs_foreground(self) -> bool:
        """Only desktop (PyAutoGUI) requires Profile B to be the active console."""
        return self.route == "desktop"

    @property
    def is_background_safe(self) -> bool:
        """mcp and browser never touch the foreground session."""
        return self.route in ("mcp", "browser")


# --- Keyword tables -------------------------------------------------------
# Ordered most-specific-first. MCP capabilities are checked before browser,
# and browser before the desktop fallback.

_MCP_KEYWORDS: dict[MCPCapability, tuple[str, ...]] = {
    "gmail": ("email", "e-mail", "gmail", "inbox", "mailbox", "send mail",
              "reply to", "compose", "draft a mail", "draft an email"),
    "calendar": ("calendar", "schedule", "agenda", "meeting", "appointment",
                 "event on", "my events", "free time", "availability"),
    "docs": ("google doc", "google docs", "the doc", "a document",
             "research doc", "notes doc", "write up", "append to doc"),
    "sheets": ("google sheet", "google sheets", "spreadsheet", "the sheet",
               "log row", "activity log", "activity sheet", "activity tracker",
               "tracking sheet", "track in sheet", "tracker",
               "log the completion", "log this run"),
}

_BROWSER_KEYWORDS: tuple[str, ...] = (
    "search", "google for", "look up", "lookup", "web", "website", "url",
    "browse", "scrape", "reddit", "news", "online", "find out", "research",
    "summarize", "machine learning", "subreddit",
)

# Goals matching the dedicated high-speed Reddit/ML scrape pipeline. Kept here so
# ALL routing keywords live in one module (ROUTING.md §5). Folded into the general
# browser route in Phase 3.
_REDDIT_SHORTCUT_KEYWORDS: tuple[str, ...] = (
    "reddit", "machine learning", "subreddit", "r/machinelearning",
)


def _contains(haystack: str, needles: tuple[str, ...]) -> Optional[str]:
    for n in needles:
        if n in haystack:
            return n
    return None


def classify_goal(goal: str) -> RoutingDecision:
    """Return the single routing decision for a natural-language goal."""
    g = (goal or "").lower()

    # 1. MCP first — most specific capability wins.
    for capability, keywords in _MCP_KEYWORDS.items():
        hit = _contains(g, keywords)
        if hit:
            return RoutingDecision(
                route="mcp",
                mcp_capability=capability,
                reason=f"matched MCP/{capability} keyword '{hit}'",
            )

    # 2. Web / DOM task -> headless browser.
    hit = _contains(g, _BROWSER_KEYWORDS)
    if hit:
        return RoutingDecision(
            route="browser",
            mcp_capability=None,
            reason=f"matched browser keyword '{hit}'",
        )

    # 3. Fallback — native desktop control (foreground only).
    return RoutingDecision(
        route="desktop",
        mcp_capability=None,
        reason="no MCP/browser keyword matched; defaulting to desktop control",
    )


def is_reddit_scrape_shortcut(goal: str) -> bool:
    """True if the goal should use the dedicated fast r/MachineLearning scraper."""
    return _contains((goal or "").lower(), _REDDIT_SHORTCUT_KEYWORDS) is not None


_APP_LAUNCH_RE = re.compile(
    r"^\s*(?:open|launch|start|run|fire up)\s+(?:the\s+)?(.+?)(?:\s+app(?:lication)?)?\s*$",
    re.IGNORECASE,
)
# Words that mean this isn't a plain native-app launch (web / file / MCP territory).
_NOT_AN_APP = (
    "http", "www.", ".com", ".org", ".net", "url", "website", "link", "tab",
    "email", "e-mail", "gmail", "inbox", "mailbox", "calendar", "doc", "sheet",
    "spreadsheet", "folder", "file", "reddit", "subreddit",
)


def parse_app_launch(goal: str) -> Optional[str]:
    """
    If the goal is a simple 'open/launch <app>' request, return the app name (for the
    session-safe open_app action). Otherwise None. Returns None for web/file/MCP-style
    'open' phrasings so those keep routing to browser/mcp.
    """
    if not goal:
        return None
    m = _APP_LAUNCH_RE.match(goal.strip())
    if not m:
        return None
    name = m.group(1).strip().strip("\"'")
    if not name or len(name) > 40:
        return None
    low = name.lower()
    if any(t in low for t in _NOT_AN_APP):
        return None
    return name
