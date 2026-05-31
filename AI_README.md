# Doppelgänger OS — Technical Architecture & Codebase Map

This document serves as an exhaustive, high-fidelity system blueprint of the **Doppelgänger OS** codebase. It is designed to be parsed directly by LLMs or developer agents to immediately understand the project’s structure, data flows, APIs, multi-profile isolation boundaries, and execution pathways.

---

## 1. System Overview & Concept

Doppelgänger OS is an autonomous macOS AI agent that lives inside a dedicated background user profile (**Profile B / Clone**) and executes delegated work (web browsing, research, Google Docs/Sheets sync, inbox polling) while the user continues working uninterrupted in their main profile (**Profile A / Commander**).

### Core Philosophy
* **Non-Disruptive:** Clicks and keystrokes are executed in the background without hijacking the user's mouse/keyboard.
* **Secure Sandbox:** Holds no credentials on the sandboxed Profile B; communications flow over highly guarded local API contracts.
* **Active Protection Guard (Failsafe):** Strictly blocks screen capture and PyAutoGUI control if the background profile is in the background, preventing privacy leaks and screen hijack of Profile A.

---

## 2. System Architecture

The system operates across a localhost loop split between two separate macOS user profiles:

```
                  PROFILE A (Commander)           │            PROFILE B (Clone)
┌─────────────────────────────────────────────────┼─────────────────────────────────────────────┐
│  ┌──────────────────┐                           │                                             │
│  │    SwiftUI       │                           │                                             │
│  │   Notch UI       │                           │                                             │
│  │  App Launcher    │◀──────────────────────────┼───────────────┐                             │
│  └────────┬─────────┘                           │               │                             │
│           │ Spawns Subprocess                   │               │                             │
│           ▼                                     │               │                             │
│  ┌──────────────────┐                           │      ┌────────┴─────────┐                   │
│  │   Orchestrator   │    Submit Actions         │      │   Agent-Server   │                   │
│  │   (Port 8420)    │───────────────────────────┼─────▶│   (Port 8421)    │                   │
│  │  Gemini Brain    │                           │      │ PyAutoGUI/Quartz │                   │
│  └────────┬─────────┘◀──────────────────────────┼──────└────────┬─────────┘                   │
│           │              Return Observations    │               │                             │
│           │                                     │               ▼ Automates                   │
│           ▼ MCP Writes                          │      ┌──────────────────┐                   │
│  ┌──────────────────┐                           │      │  Google Chrome   │                   │
│  │  Google Cloud    │                           │      │ (CDP Port 9222)  │                   │
│  │   Docs/Sheets    │                           │      └──────────────────┘                   │
│  └──────────────────┘                           │                                             │
└─────────────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 3. Directory & File Taxonomy

```
Quackhacks-2026/
├── shared/                         # Zero-dependency contract and transplant libraries
│   ├── contract.py                 # Pydantic core message validation models
│   └── session_transplant.py       # Extract/filter whitelisted cookies from Profile A Chrome
│
├── orchestrator/                   # The "Brain" (Runs on Profile A, Port 8420)
│   ├── main.py                     # Main vision-action loop, BigQuery interface, Notch UI sync
│   ├── mcp_google.py               # Google Docs & Sheets MCP integrations
│   ├── requirements.txt            # Orchestrator dependencies (GenAI, BigQuery, FastAPi)
│   └── personas/                   # Markdown behavior templates shaping Gemini's tone
│
├── agent-server/                   # The "Hands & Eyes" (Runs on Profile B, Port 8421)
│   ├── main.py                     # Action execution endpoint, active console check, Chrome CDP
│   └── requirements.txt            # Server dependencies (FastAPI, PyAutoGUI, Playwright, PyObjC)
│
├── doppelganger-ui/                # macOS Status Bar & Notch Menu App (SwiftUI)
│   └── Sources/
│       ├── App.swift               # Application lifecycle & background HUD configuration
│       ├── ContentView.swift       # Glassmorphism notch pill, chat logs, action nudge drawer
│       ├── PipView.swift           # Real-time MJPEG live video stream consumer
│       └── ProcessSupervisor.swift # Async Python subprocess supervisor (spawns Port 8420)
│
├── verify_pipeline.py              # Smoke test to run end-to-end Reddit scraper flow
├── verify_transplant.py            # Diagnostic script to test Chrome cookie transplanting
└── doppelganger-os-prd.md          # Comprehensive Product Requirement Document
```

---

## 4. API & Data Contracts

All inter-profile communication is validated via `shared/contract.py` using **Pydantic**:

### `CommandModel` (Orchestrator -> Agent-Server)
* **`path`**: `Literal["computer_use", "browser_use", "noop"]`
* **`action`**: `Literal["click", "type", "key", "read", "navigate", "scroll", "hover", "screenshot", "poll_mail"]`
* **`args`**: `Dict[str, Any]` (e.g. `{"x": 100, "y": 200, "text": "Apple stock price\n", "url": "google.com", "selector": "input[name='q']"}`)

### `ObservationModel` (Agent-Server -> Orchestrator)
* **`screenshot_url`**: `http://localhost:8421/frame.jpg` (Returns either active desktop screenshot, secure failsafe placeholder, or headless browser viewport)
* **`screen_state`**: `Literal["ok", "modal", "error", "stuck", "background_lock"]`
* **`result`**: `Dict[str, Any]` containing command execution details or scraped output.

### `MailNotificationModel` (Agent-Server -> Orchestrator)
* Emitted by background AppleScript unread mail poll:
* **`unread_count`**: `int`
* **`latest_sender`**: `str`
* **`latest_subject`**: `str`

---

## 5. Execution Pathways

Doppelgänger OS dynamically routes tasks through three distinct execution layers:

### A. Headless Background Browser Loop (Chrome CDP)
* **Trigger:** Web-based goals (searching, Google Docs, Sheets, email) while Profile B is in the background.
* **Mechanism:**
  1. The Orchestrator detects Profile B is in the background (`active_console = False` on Port 8421 root).
  2. It injects a hint instructing Gemini to use `action="browser_use"`.
  3. The `agent-server` connects to Chrome running on **Port 9222** via Playwright.
  4. Actions (navigate, type, click, scroll) are executed natively within Chrome's DOM completely headlessly.
  5. The viewport screenshot is captured and piped to the SwiftUI Notch PiP feed, showing live web browsing without disrupting Profile A.

### B. Attended Desktop Computer Use (PyAutoGUI)
* **Trigger:** Visual control of native macOS applications (Spotlight, Finder).
* **Mechanism:**
  1. The Orchestrator checks if `active_console` is `True` (meaning you have Fast-User-Switched into Profile B).
  2. The agent executes clicks, keystrokes, and global captures via PyAutoGUI and Pillow.
  3. If you switch back to Profile A, the failsafe immediately engages: screen capture returns a secure dark-theme placeholder, and input commands return `screen_state = "background_lock"`.
  4. The Orchestrator pauses the loop and nudges you through the Notch UI: *"Please fast-user-switch to Profile B to allow visual tasks!"*.

### C. Programmatic Scraper Shortcut
* **Trigger:** Scrape/summarize Machine Learning subreddit.
* **Mechanism:** Bypasses the visual brain loop completely to run a direct, high-speed Playwright scrape of Reddit (falling back to Hacker News AI API if Reddit is blocked or offline), summarizing the articles via Gemini and syncing to Docs/Sheets instantly.

---

## 6. Security Failsafe & Guardrails

To protect the user session in Profile A, `agent-server/main.py` implements native macOS console session detection:

```python
def is_profile_b_active_console() -> bool:
    try:
        import Quartz
        session_dict = Quartz.CGSessionCopyCurrentDictionary()
        if session_dict is None:
            return False
        on_console = session_dict.get("kCGSSessionOnConsoleKey", 0) == 1
        is_locked = session_dict.get("CGSSessionScreenIsLocked", 0) == 1
        return on_console and not is_locked
    except Exception:
        return True
```

### Action Safeguard Matrix:
| Profile B Session State | Web CDP Tasks (`browser_use`) | Desktop Tasks (`computer_use`) | PiP Video Feed Screenshot (`/frame.jpg`) |
| :--- | :--- | :--- | :--- |
| **Active Console (Foreground)** | Allowed | Allowed (PyAutoGUI active) | Captures active Profile B Desktop |
| **Inactive Session (Background)** | Allowed (Headless CDP) | **BLOCKED** (Returns `background_lock`) | Captures **Headless Chrome Viewport** (or Failsafe Placeholder) |

---

## 7. Environment & Configuration Settings

Settings live in `orchestrator/.env` (on Profile A ONLY) to isolate credentials from Profile B:

```bash
# Core API Credentials
GOOGLE_API_KEY="AIzaSy..."          # Gemini models & vision loops
ELEVENLABS_API_KEY="el_..."         # High-fidelity speech narration (optional)

# Google Workspace / Cloud Settings
GOOGLE_DOC_ID="1x2y3z..."           # Target Google Doc for research notes
GOOGLE_SHEET_ID="4a5b6c..."         # Target Google Sheet for activity logs
GCP_PROJECT_ID="doppelganger-bq"    # BigQuery database project ID (memory write-through)

# Inter-profile Ports
ORCHESTRATOR_PORT=8420               # Port the orchestrator process listens on
AGENT_SERVER_PORT=8421               # Port the agent-server process listens on
CDP_PORT=9222                        # Chrome DevTools Protocol port (Profile B Chrome)

# Session Cookie Transplant Module
ENABLE_SESSION_TRANSPLANT="true"     # Transfer whitelisted cookies from Profile A to B
PROFILE_A_CDP_PORT=9223              # Port to connect to Profile A Chrome debugging session
```

---

## 8. Runbook & Startup Flow

1. **Start Chrome in Profile B with debugging enabled:**
   `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222`
2. **Launch the agent-server inside Profile B:**
   `python3 agent-server/main.py`
3. **Launch the SwiftUI Notch app in Profile A:**
   * The app will automatically spawn the Python Orchestrator (`orchestrator/main.py`) via `ProcessSupervisor.swift`.
   * The Status Bar/Notch Pill will display `Doppelgänger: Ready` and open the PiP feed stream connected to `:8421/stream`.
4. **Delegate tasks:** Type or speak to the Notch UI. Visual web tasks will run headlessly, desktop tasks will trigger active-console nudges.
