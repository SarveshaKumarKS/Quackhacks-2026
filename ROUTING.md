# Doppelgänger OS — Execution Routing Rules

This document is the **source of truth** for deciding *which tool* the agent uses to
perform any delegated task. Code in `orchestrator/main.py` and `agent-server/main.py`
must conform to these rules. Where it does not yet, see §6 (Compliance Gaps).

There are exactly **three execution surfaces**, ranked by reliability and how little
they disrupt the user. Always use the **highest-ranked surface that can do the job.**

---

## 1. The three tools (plain English)

### Tier 1 — MCP / API  *(first choice)*
> "Talk to the service directly through its API."

- **Module:** `orchestrator/mcp_google.py` (Docs, Sheets, Gmail, Calendar) + BigQuery memory.
- **Use when** the task maps to a known API: append to a Doc, log a Sheet row,
  send or draft an email, read the calendar, read/write agent memory.
- **Why first:** deterministic, no screen, no browser, **works regardless of which
  profile is in the foreground.** No pixels, no DOM, no failure modes from UI changes.
- **Runs on:** Profile A (orchestrator) — it holds the credentials.

### Tier 2 — browser_use / Headless CDP  *(second choice)*
> "Drive a real Chrome over CDP because no API exists for this."

- **Module:** `agent-server/main.py` → Playwright over Chrome DevTools Protocol (port 9222).
- **Use when** the task is a web/DOM task with **no MCP**: web search, scraping a site,
  navigating / clicking / typing / scrolling on an arbitrary web page.
- **Why second:** runs in the background (Profile B can be hidden), so it is
  non-disruptive — but it is DOM automation, which is more fragile than an API and
  depends on Chrome being up on :9222 and logged in.
- **Runs on:** Profile B (agent-server).

### Tier 3 — computer_use / PyAutoGUI  *(last resort)*
> "Click real pixels on the macOS desktop."

- **Module:** `agent-server/main.py` → PyAutoGUI + global screen capture.
- **Use ONLY for** native macOS apps that have no API and no web equivalent:
  Spotlight, Finder, System Settings, native third-party app UIs.
- **Hard requirement:** **Profile B must be the active console (foreground).**
  If it is in the background, this tier is **blocked**; pause and nudge the user to
  Fast-User-Switch into Profile B.
- **Runs on:** Profile B (agent-server).

---

## 2. The decision ladder (run top to bottom, stop at first match)

```
1. Can an MCP/API do this task?        ──► use Tier 1 (MCP).        [Docs/Sheets/Gmail/Calendar/Memory]
2. Else, is it a web / DOM task?       ──► use Tier 2 (browser_use, headless).
3. Else (native desktop app only)?     ──► use Tier 3 (computer_use),
                                              but ONLY if Profile B is foreground;
                                              otherwise pause + nudge to switch.
```

**Tie-breakers**
- A web task that *also* has an API (e.g. "search Gmail", "edit the Google Doc")
  is an **API task** — Tier 1 wins. MCP always beats the browser.
- Never use computer_use (pixels) to do something a browser or API can do.
- Never use a browser to do something an API can do.

---

## 3. Profile-state interaction (safety matrix)

| Profile B session state | Tier 1 (MCP) | Tier 2 (browser_use) | Tier 3 (computer_use) | PiP `/frame.jpg` |
| :--- | :--- | :--- | :--- | :--- |
| **Foreground (active console)** | Allowed | Allowed | Allowed | Live Profile B desktop |
| **Background (switched out / locked)** | Allowed | Allowed (headless) | **BLOCKED → nudge** | Headless Chrome viewport, else failsafe placeholder |
| **Unknown / detection error** | Allowed | Allowed | **BLOCKED (fail closed)** | Failsafe placeholder |

MCP and browser_use are profile-independent — they never touch the foreground session,
so they are always allowed. Only Tier 3 is gated by profile state.

---

## 4. The overriding safety rule: **fail closed**

If the system cannot reliably determine whether Profile B is the foreground console,
it must **assume background** and **block computer_use**. A detection error must never
result in PyAutoGUI input or a global screen capture running.

- `is_profile_b_active_console()` must return **False** on any exception.
- The orchestrator's read of `active_console` must default to **False** when missing.

This is the inverse of the current code (see §6) and is non-negotiable: a guard that
fails open is not a guard.

---

## 5. One classifier, not many keyword lists

Routing must be decided by **a single shared classifier** that returns exactly one of:

```
route ∈ { "mcp", "browser", "desktop" }
```

…optionally with the specific MCP capability for `mcp` (doc / sheet / gmail / calendar).
The orchestrator and any hints sent to Gemini consume this one result. We do **not**
maintain separate, overlapping keyword sets (`is_programmatic`, `is_web_task`, …) that
can disagree with each other.

---

## 6. Compliance gaps (current code vs. these rules)

These are the known divergences to fix in the follow-up implementation pass:

1. **No MCP route in the router.** Brain action enum is
   `[click, type, key, noop, scroll, browser_use, completed]`
   (`orchestrator/main.py` ~L500). Docs/Sheets writes are hardcoded only inside the
   Reddit scraper shortcut; `send_gmail_message` and `check_google_calendar`
   (`mcp_google.py` L121, L154) are **dead code**. → Add an explicit `mcp` path and
   route API tasks to it before the visual loop. *(Decision: MCP always wins.)*

2. **Email routed to the browser.** "email" is treated as a `is_web_task`
   (`orchestrator/main.py` ~L421) and pushed to headless browser in the background,
   instead of the Gmail API that already exists. → Email/calendar/docs = Tier 1.

3. **Web tasks pixel-clicked when foreground.** System prompt tells Gemini to use
   `browser_use` only for "Reddit / web scraping," else click the screen
   (`orchestrator/main.py` ~L466). → All web/DOM tasks must use browser_use, never
   computer_use.

4. **Fail-open safety (two places).** `is_profile_b_active_console()` returns `True`
   on exception (`agent-server/main.py` ~L66); orchestrator reads
   `active_console` defaulting to `True` (`orchestrator/main.py` ~L419).
   → Both must fail closed (return/default `False`).

5. **Overlapping keyword heuristics.** `is_programmatic` vs `is_web_task` are separate
   and inconsistent. → Replace with the single classifier in §5.

---

## 6b. Compound tasks (the planner)

A single instruction may chain several tasks across tiers
(e.g. *"summarize a subreddit → draft an email → update the doc → save to Notes"*).
These are handled by a planner/sequencer layer above the router:

1. `planner.looks_compound(goal)` — cheap gate; simple goals skip planning entirely.
2. If compound, Gemini decomposes the goal into an ordered list of atomic sub-tasks.
3. The sequencer runs each sub-task through the **same** `classify_goal` router (so every
   step obeys the tiers above), carrying each step's text output forward as shared
   context for later steps (the summary feeds the email, the doc, and the Notes copy).
4. Irreversible steps (email send) still hit the confirm-before-send gate; desktop steps
   still require Profile B foreground (else nudge).

The planner never bypasses the routing rules — it orchestrates them.

## 7. Quick reference

| Goal example | Route |
| :--- | :--- |
| "Append the summary to the research doc" | **MCP** (Docs) |
| "Log this run in the activity sheet" | **MCP** (Sheets) |
| "Draft / send an email to the client" | **MCP** (Gmail) |
| "What's on my calendar?" | **MCP** (Calendar) |
| "Search Google for the latest on X" | **browser_use** |
| "Scrape r/MachineLearning" | **browser_use** |
| "Fill out this web form" | **browser_use** |
| "Open Spotlight and launch Notes" | **computer_use** (foreground only) |
| "Drag this file in Finder" | **computer_use** (foreground only) |
