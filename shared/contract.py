from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class CommandModel(BaseModel):
    """
    Message model sent from Orchestrator (Profile A) -> Agent-Server (Profile B).
    Tells the agent-server which action to execute natively.
    """
    type: Literal["action"] = "action"
    path: Literal["computer_use", "browser_use", "mcp", "noop"] = Field(
        ...,
        description="The routing pathway for this action. See ROUTING.md: "
                    "mcp (API, first choice) > browser_use (headless web) > computer_use (desktop, last resort)."
    )
    action: Literal[
        # computer_use / browser_use verbs
        "click", "type", "key", "read", "extract", "navigate", "scroll", "hover", "screenshot", "poll_mail",
        # mcp verbs (Google Docs / Sheets / Gmail / Calendar)
        "send_email", "append_doc", "append_sheet", "read_calendar",
    ] = Field(
        ...,
        description="The action verb to execute on the desktop, browser session, or MCP/API surface."
    )
    args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic arguments needed for the action (e.g., {'x': 100, 'y': 200, 'text': 'hello'})."
    )

class ObservationModel(BaseModel):
    """
    Observation model returned from Agent-Server (Profile B) -> Orchestrator (Profile A).
    Reports what the agent sees on-screen or returns the result of the action.
    """
    type: Literal["observation"] = "observation"
    screenshot_url: Optional[str] = Field(
        None,
        description="URL to retrieve the latest full screen frame (usually http://localhost:8421/frame.jpg)."
    )
    screen_state: Literal["ok", "modal", "error", "stuck"] = Field(
        "ok",
        description="Indicates vision safety state to trigger the stuck-detector."
    )
    result: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action outcomes (e.g., {'success': True, 'scraped_text': '...'}) or error messages."
    )

class MailNotificationModel(BaseModel):
    """
    Stateless inbox update model returned from Agent-Server (Profile B) -> Orchestrator (Profile A).
    Represents the output of the AppleScript inbox poll.
    """
    type: Literal["mail_notification"] = "mail_notification"
    unread_count: int = Field(0, ge=0, description="Total number of unread emails in Mail.app.")
    latest_sender: Optional[str] = Field(None, description="Sender of the most recent unread email.")
    latest_subject: Optional[str] = Field(None, description="Subject of the most recent unread email.")
    timestamp: str = Field(..., description="ISO 8601 timestamp of when the poll completed.")
