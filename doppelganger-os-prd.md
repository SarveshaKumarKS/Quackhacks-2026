# Doppelgänger OS — Product Requirements Document

**Version:** 1.1 (Hackathon Build Spec)
**Event:** QuackHacks — targeting the Google track (best use of Google / Gemini / GCP) and the overall grand prize
**Team size:** 2
**Build window:** 24 hours
**Status:** Locked for build

**Changelog v1.1:** Removed the `/Users/Shared` local shared folder. All inter-profile task output now flows through Google cloud documents (a Google Doc for notes, a Google Sheet for the tracker) via MCP — matching the proven reference approach. Persona files remain in the agent's own per-user home directory.

---

## How to read this document

This PRD is scoped for a 24-hour, 2-person hackathon, not a general engineering org. Every requirement is tagged with a priority so that under time pressure you cut from the bottom, never the top:

- **[P0]** — Must exist or there is no demo. Build first, protect ruthlessly.
- **[P1]** — Strongly wanted; makes the demo land. Build after every P0 works end-to-end.
- **[P2]** — Stretch. Touch only if P0 and P1 are done and rehearsed.

A recurring rule throughout: **a hackathon demo requires the convincing *appearance* of a complete product, demonstrated in five minutes — not a shippable product.** Wherever a "real" implementation costs hours for something a judge cannot see, this document specifies the thinnest honest version that reads as complete.

---

## Section 1 — Executive Summary & Core Value Proposition

### 1.1 Executive Summary

Doppelgänger OS is an autonomous AI agent that lives inside a dedicated macOS user profile on your own Mac and does delegated work for you — browsing, drafting, updating documents, and handling routine tasks — while you keep working, uninterrupted, in your own profile. Unlike agents that hijack your mouse and keyboard or run on someone else's cloud, the Doppelgänger operates in its own sandboxed session on your hardware, visible to you in real time through a Picture-in-Picture feed that hangs from the webcam notch. It has its own screen, its own files, and its own logged-in apps; if it misfires, your real workspace is untouched. It knows when it doesn't know — pausing to ask you at genuine decision points — and it remembers what you tell it, so it gets more useful every time you use it. Anyone can set up their own Doppelgänger through a short web onboarding flow that builds a personal profile and hands them an installer.

### 1.2 The Core Problem

People want to delegate the constant low-stakes noise of digital work — triaging an incoming email, looking something up, updating a tracker — but the two existing options both fail. A cloud agent cannot touch the apps, accounts, and files that live on your actual machine, and it has no real context about you. A local agent that drives your own mouse and keyboard makes your computer unusable while it runs — you cannot delegate a task *and* keep working, which defeats the entire purpose. The result is that "AI that does your work" still costs you the thing you were trying to protect: your attention and your machine.

### 1.3 The Core Insight

macOS Fast User Switching lets a second user session stay fully signed in and running in the background while you use your own. Doppelgänger OS gives the agent that second session. This single architectural choice resolves the central tension: the agent works on *your* Mac — with your apps, your logins, your accounts — yet in a hard-walled session that never contends with your mouse, your screen, or your work. You delegate and keep going. You watch over its shoulder through the notch when you want to; you ignore it when you don't.

### 1.4 Core Value Proposition

For knowledge workers who want to offload routine digital tasks without surrendering their computer, Doppelgänger OS is an AI agent that works *beside* you instead of *through* you. It is the only approach that combines the full capability and context of running natively on your own machine — real apps, real accounts — with the safety and non-interference of complete session isolation. It acts through the same interfaces a person uses (operating any app by seeing and clicking, controlling the browser directly, and calling structured tools), it escalates to you only when a decision genuinely requires you, and it compounds in usefulness by remembering your corrections in a durable, queryable memory.

### 1.5 Why This Wins (Judging Framing)

- **A real architectural idea, not a wrapper.** The Fast-User-Switching sandbox is a genuine systems insight that solves a real UX problem, and it demos viscerally — judges *watch* an AI working in its own desktop, then switch into that desktop to find it there.
- **Deep, deliberate use of the Google stack.** The agent's perception-and-action brain is Google's Gemini Computer Use model; its durable, queryable memory is BigQuery; its task output lands in Google Docs/Sheets via MCP; the whole system runs on Google Cloud. Google integration is load-bearing, not decorative.
- **Honest, visible intelligence.** "Knows when to ask" and "learns from what you tell it" are demonstrated live — an ambiguity triggers a question, your answer is written to BigQuery, and the learned fact is shown on screen — rather than claimed.
- **Safety as a feature, not a disclaimer.** Sandbox isolation and human-in-the-loop escalation are built into the architecture, which is exactly what makes delegating to it trustworthy.
- **A complete product story.** Anyone can onboard on the web, generate their own twin's persona, and install it — the full arc from stranger to running agent is demonstrable.

---

## Section 2 — Target Audience & Core Pain Points

### 2.1 Primary Persona — "The Delegator"

A knowledge worker (developer, founder, analyst, operator) who lives in their Mac all day, juggles a steady stream of small interruptions, and would happily hand off routine tasks — *if* doing so did not cost them their machine or their focus. They are comfortable with AI tools, skeptical of giving an agent unsupervised control, and protective of their primary workflow. They value being able to *watch* and *intervene*.

### 2.2 Core Pain Points

| Pain point | How Doppelgänger OS addresses it |
|---|---|
| "An agent taking over my mouse/keyboard makes my computer unusable." | The agent runs in a separate session; your input devices and screen are never touched. |
| "Cloud agents can't reach my real apps and logins." | Runs natively on your Mac with access to a real, logged-in profile and your cloud documents. |
| "I don't trust an agent to act unsupervised in my name." | Live PiP feed, human-in-the-loop escalation at genuine decision points, and a hard stop before any irreversible action. |
| "Generic agents don't know how I work or write." | A personal profile (built during onboarding) shapes how the twin writes and acts; corrections persist and compound. |
| "Agents repeat the same mistakes." | A durable memory (BigQuery) records corrections so the twin asks once, then remembers. |

### 2.3 Who this is NOT for (scope honesty)

Not a fully autonomous "set it and forget it" agent, not a multi-user enterprise deployment, and not a Windows/Linux product. The hackathon build targets a single user on a single Mac with a supervised, human-in-the-loop model.

---

## Section 3 — The "Golden Path" Hackathon Scope

### 3.1 Scope philosophy

One hardened, rehearsed hero task that threads every component and every sponsor into a single five-minute narrative — not a suite of independent features. The agent is *architecturally* general (it can use any app, the browser, and structured tools); the *demo* runs a known path rehearsed dozens of times. The general capability is the pitch; the rehearsed path is the demo.

### 3.2 The Hero Task (the one continuous story)

**Scenario:** While the user works in their own profile, a real email arrives in the twin's profile asking the user to summarize what people are saying about a topic on "the usual subreddit" and to log it. The twin notices, offers to help, does the research and the busywork, asks for clarification when genuinely ambiguous, learns from the answer, and prepares a reply for the user's review.

**End-to-end flow:**

1. A real email lands in Mail.app in Profile B (the user sends it from their phone — genuinely real, just timed). The twin detects the new message.
2. The notch UI drops down with a proactive nudge: *"[USER_NAME], you've got a new email from [sender] asking for a Reddit summary — want me to handle it?"* (spoken by the twin's Jarvis voice, shown as text).
3. The user approves (voice → editable notch text → Enter).
4. The twin opens the browser and navigates to the subreddit via **browser-use** (CDP/DOM), reads the top 3 posts.
5. **Ambiguity fork (the featured "ask for help" beat):** the email said "the usual subreddit"/"the client," which the twin does not know. It pauses and asks: *"Which subreddit did you mean — r/MachineLearning or r/LocalLLaMA?"* (and/or *"Which client is this — Acme or Globex?"*). The user answers. **The answer is written to BigQuery** as a learned preference.
6. The twin writes the top 3 findings into a **Google Doc** and updates a tracking **Google Sheet**, both **via MCP**.
7. The twin drafts a reply email in the **user's written persona** (pulled from the persona profile), and **stops at the draft** — it does not auto-send (live-demo safety guardrail).
8. The twin's **Jarvis voice** (ElevenLabs) summarizes what it did, addressing the user by name.
9. **Memory reveal:** the presenter flips to the BigQuery console and runs a `SELECT` showing the learned preference row, timestamped — visible proof that the twin learned and will not ask again.
10. **[P1] Theatrical reveal:** trigger Fast User Switching; the macOS cube animation spins; the audience lands in Profile B's live desktop to find the twin's work there.

### 3.3 In scope

- One Mac, Fast User Switching, Profile A (Commander) + Profile B (Clone).
- Notch UI on Profile A: proactive nudge, chat, voice input, PiP feed.
- Live MJPEG PiP feed of Profile B.
- Three action paths: Gemini Computer Use (native desktop), browser-use (web), MCP (Docs/Sheets/email/calendar).
- BigQuery durable memory (persona + learned corrections) with live `SELECT` reveal.
- ElevenLabs Jarvis voice that addresses the user by name.
- Four-trigger confidence-gated escalation (the "knows when to ask" behavior).
- Thin web onboarding: polished site + persona-generating form, stubbed auth, shown-not-shipped installer.

### 3.4 Explicitly OUT of scope (see Section 8 for the full list)

Local shared folder (`/Users/Shared`); real OAuth scraping pipeline; voice cloning of the user; real authentication backend; signed/notarized installer built live; reinforcement-learning training loop (HEX / Prime Intellect); cookie cloning; Microsoft Teams/Outlook integration; multi-user support; Windows/Linux.

### 3.5 Demo timing budget (5:00)

| Time | Beat | Risk | Fallback |
|---|---|---|---|
| 0:00–0:30 | Setup: explain the twin has its own profile | None | — |
| 0:30–1:30 | Proactive nudge; user approves | Low | Trigger nudge manually |
| 1:30–2:40 | Live work in PiP (browse, write, ask) | **Highest** | Human nudge past snags; pre-warmed steps |
| 2:40–3:40 | Memory reveal (BigQuery SELECT) | Low | Pre-run query screenshot |
| 3:40–4:20 | Jarvis voice summary; stop at draft | Low | Pre-rendered audio clip |
| 4:20–5:00 | [P1] FUS cube reveal + close | Low | Skip; close verbally |
| buffer | ~30s for Q&A / recovery | — | — |

The riskiest live element (the agent acting) is placed early while attention and patience are highest; the un-failable applause beats (memory reveal, voice, cube) are placed late as guaranteed closers.

---

## Section 4 — Technical Architecture & Data Flow

### 4.1 Topology (validated against a known-working reference implementation)

Two halves on one Mac, communicating over `localhost`. No cloud relay for inter-profile communication. Task *output* lives in Google cloud documents; there is no local shared folder between profiles.

```
PROFILE A — Commander (the user's session)        PROFILE B — Clone (background session)
┌────────────────────────────────────────┐       ┌──────────────────────────────────────┐
│ Notch UI app (SwiftUI)                   │       │ agent-server  :8421                   │
│   ├─ Orchestrator  :8420                 │◄─────►│   ├─ MJPEG screen stream (capture loop)│
│   │   ├─ holds API keys                  │ local │   ├─ action executor (click/type/key) │
│   │   ├─ Gemini Computer Use calls       │ host  │   └─ AppleScript Mail.app poll        │
│   │   ├─ tool routing (3 paths)          │       │                                        │
│   │   └─ BigQuery read/write             │       │ browser (CDP) :9222  for browser-use  │
│   ├─ PiP viewer (consumes MJPEG)         │       │ Mail.app (Gmail + Outlook logged in)  │
│   ├─ voice in (Web Speech / native STT)  │       │ Numbers/Safari/Chrome                 │
│   └─ voice out (ElevenLabs Jarvis)       │       └──────────────────────────────────────┘
└────────────────────────────────────────┘
                  │
                  ▼
        Google Cloud — BigQuery (durable memory: persona + learned corrections)
        Google Cloud — Gemini Computer Use model (perception + action)
        Google Cloud — Docs & Sheets (task output, written via MCP)
        ElevenLabs — Jarvis voice synthesis

TASK OUTPUT:  Google Doc (notes) + Google Sheet (tracker), via MCP — NO local shared folder.
PERSONA:      agent's own per-user home dir (e.g. ~/.doppelganger/), NOT shared between profiles.
```

### 4.2 Division of labor

- **Orchestrator (Profile A):** the brain. Holds all API keys, makes the Gemini Computer Use calls, decides which of the three action paths handles each step, performs BigQuery reads/writes, drives MCP calls to Docs/Sheets, and drives the notch UI. Keys never live in the sandboxed profile.
- **agent-server (Profile B):** the hands and eyes. Captures the screen (MJPEG loop), executes the concrete UI actions the orchestrator sends (`pyautogui`/AppleScript), and runs the Mail.app poll. Stateless with respect to "what to do next" — it only does what it is told and reports what it sees.

### 4.3 The three action paths

| Path | Used for | Mechanism | Why |
|---|---|---|---|
| **Gemini Computer Use** | Native macOS apps (Mail) — the signature flex | Screenshot → model returns `click(x,y)` / `type` → executor runs it | "Uses your computer like a human"; no per-app API needed |
| **browser-use (CDP)** | Web tasks (Reddit research) | Direct DOM/devtools control of the browser | Faster and more reliable than vision for the web; the riskiest-by-vision step made robust |
| **MCP connectors** | Structured services (Google Docs, Sheets, email send, calendar) | Structured tool/function calls to Google APIs | Reliable, near-impossible to misfire; ideal for the notes/tracker output |

**Model:** use a Computer-Use-capable Gemini model — `gemini-3-flash-preview` for the loop (low latency/cost; Computer Use is *not* supported on the GA Gemini 3.5 Flash, so pin the preview), with a Pro Computer-Use variant as a fallback if Flash misreads the screen during rehearsal. Verify GCP credits are applied to the project so rehearsal isn't throttled to free-tier quotas.

### 4.4 Memory model (BigQuery — durable brain)

Google cloud documents (Doc/Sheet) hold the task *output*. BigQuery holds the twin's durable *knowledge*: persona/preferences and learned corrections that should persist and compound across every session. To keep the network off the critical path, use **write-through, read-local**: the agent reads from a local cache (instant, cannot fail mid-demo) and writes every learned fact through to both the cache and BigQuery. BigQuery is the durable backing store and the on-screen proof; if it hiccups live, the agent does not stutter.

Single table:

```sql
CREATE TABLE agent_memory (
  id           INT64,
  session_id   STRING,
  memory_type  STRING,   -- 'persona' | 'preference' | 'correction' | 'action_log'
  content      STRING,   -- e.g. "usual subreddit = r/MachineLearning"
  created_at   TIMESTAMP
);
```

Retrieval is recency/keyword based (grab recent rows by `session_id`/`memory_type`, inject into the prompt). No vector search is required for the demo; the schema supports adding Vertex AI / BigQuery vector search later — a clean answer to "how does it scale?"

### 4.5 The stuck-detector (confidence-gated escalation)

Not autonomous "stuck detection" (a research problem) and not scripted spoon-feeding. The agent acts autonomously and escalates to the user only when one of four concrete triggers fires:

1. **Irreversible / high-stakes action** about to occur (send, delete, overwrite) — keyword check on the planned action. *Always ask.* (This is also the send-safety guardrail.)
2. **Unexpected screen state** — a modal, alert, error, or login prompt. *Vision yes/no check.*
3. **Low self-confidence** — the model is asked to rate 0–10 how sure it is of the next action and flag ambiguity; below threshold, *ask.*
4. **Loop detected** — same action twice with no screen change. *Pure code: compare last two states.*

Three of the four are plain code; the fourth is one line in the prompt. When the agent escalates and the user answers, the pair is written to BigQuery; next time a similar trigger fires, the agent checks BigQuery first ("have I been told how to handle this?") and proceeds silently if so. That is the honest "learns from feedback" loop — a memory loop, explicitly *not* reinforcement learning.

### 4.6 Authentication strategy (the OAuth swamp, engineered away)

The twin acts *through the screen and through MCP*, inheriting sessions a human already established:
- **Email:** Gmail and Outlook are added to **Mail.app on Profile B once, by hand, beforehand** (normal account setup; Apple handles the OAuth internally). The twin reads and composes via the app — no Gmail/Graph API, no cookie cloning, no scopes.
- **Monitoring new mail:** a lightweight **AppleScript** poll of Mail.app on Profile B reports unread count + latest sender/subject. Real monitoring of real mail, ~minutes of code, zero OAuth.
- **Structured actions (Docs/Sheets/calendar):** via MCP connectors to Google services, authorized once during setup.

### 4.7 The screen pipe (highest-risk component — build first)

Cross-user screen streaming is the single hardest, most environment-specific piece (confirmed by the reference project, which hedged with two mechanisms). Build the **simplest sufficient version first**: an MJPEG loop in the agent-server — capture the Profile B screen (Quartz), encode JPEG frames, stream over HTTP on `:8421`; the PiP viewer in the notch consumes the stream. This is simpler than wrangling a full VNC server and is enough for the PiP feed.

**Mandatory manual setup runbook (the permission landmine):**
1. Create/provision the Profile B user account and install the agent-server as a LaunchAgent.
2. Switch *into* Profile B. Trigger a Quartz screen-capture call to raise the **Screen Recording** permission prompt; click **Allow**. Grant **Accessibility** permission for synthetic input.
3. Switch back to Profile A; restart the agent-server so it picks up the permission.
4. Run a smoke test: confirm PiP frames arrive in the notch and a test click executes in Profile B.

Do this on the actual demo machine, before building features that depend on Profile B. Synthetic input into a non-foreground session is fragile; rehearse the demo in the exact session state you will present in.

### 4.8 Onboarding & distribution architecture (thin)

- **Website (real, thin):** Next.js + Tailwind. Landing page + multi-step onboarding (welcome → persona form → preview → download). Deploy on Vercel or Cloud Run.
- **Persona form (the elegant collapse):** a short questionnaire (name, role, sign-off style, tone, key contacts/projects) generates the **persona markdown files the agent reads** — the same output the reference project's heavy scraping pipeline produced, from a 2-minute form. These files live in the agent's own per-user home directory and are the contract that links onboarding to the agent.
- **Auth:** stubbed for the demo (a "sign in" button that proceeds). Production answer: "standard Auth0 integration."
- **Installer:** **shown, not shipped.** The download button and a setup screen present the install story; the demo machine is pre-provisioned by hand. **No live notarization** (paid Apple account + multi-hour, failure-prone process — worst time-to-payoff item in the build).

---

## Section 5 — Functional Requirements (User Stories & Acceptance Criteria)

> Format: **As a** [user], **I want** [capability], **so that** [value]. Acceptance criteria are demo-observable.

### FR-1 [P0] Proactive email detection & nudge
**As** the user, **I want** the twin to notice an incoming email and offer to help, **so that** I can delegate without monitoring my inbox.
- **AC1:** When a new unread email arrives in Mail.app (Profile B), the notch UI surfaces a nudge within ~10s.
- **AC2:** The nudge names the sender and summarizes the ask, and addresses the user by name.
- **AC3:** The user can approve or dismiss from the notch.

### FR-2 [P0] Voice command input
**As** the user, **I want** to speak my approval/command and have it transcribed, **so that** I don't break my flow to type.
- **AC1:** Speaking populates editable text in the notch (native macOS speech recognition or Web Speech equivalent).
- **AC2:** The user can edit the transcript and press Enter to send (edit-before-send guard).
- **AC3:** A mis-transcription is correctable in one keystroke before anything is sent to the agent.

### FR-3 [P0] Web research via browser-use
**As** the user, **I want** the twin to read a subreddit and extract the top 3 posts, **so that** I get a summary without doing it myself.
- **AC1:** The twin navigates to the target subreddit via CDP and extracts the top 3 post titles.
- **AC2:** Progress is visible in the PiP feed.
- **AC3:** A blocking popup (cookie/login) triggers escalation rather than a silent failure (see FR-7).

### FR-4 [P0] Clarification fork with learning
**As** the user, **I want** the twin to ask when it genuinely doesn't know, **so that** it doesn't guess — and to remember my answer.
- **AC1:** On a defined ambiguity ("the usual subreddit"/"which client"), the twin pauses and asks via the notch + Jarvis voice.
- **AC2:** The user's answer is applied to continue the task.
- **AC3:** The answer is written to BigQuery as `memory_type='preference'` with a timestamp.
- **AC4 [P1]:** On a subsequent similar step, the twin reads the stored preference and does **not** re-ask.

### FR-5 [P0] Cloud-document output
**As** the user, **I want** the findings written to a notes document and a tracker, **so that** the output lands where I can use it.
- **AC1:** The top 3 findings are written to a **Google Doc** via MCP.
- **AC2:** A tracking **Google Sheet** is updated via MCP with the findings.
- **AC3:** Both documents are accessible to the user from their own profile/browser (the cloud is the shared surface — no local shared folder).

### FR-6 [P0] Persona-shaped reply draft with send guardrail
**As** the user, **I want** the twin to draft a reply that sounds like me but not send it, **so that** I stay in control of what goes out in my name.
- **AC1:** A reply draft is composed in Mail.app using the user's persona (tone, sign-off).
- **AC2:** The twin **stops at the draft** and never auto-sends (irreversible-action guardrail).
- **AC3:** Sending, if shown at all, requires explicit user action.

### FR-7 [P0] Confidence-gated escalation
**As** the user, **I want** to be interrupted only when needed, **so that** delegation is real and not constant babysitting.
- **AC1:** Each of the four triggers (irreversible / unexpected screen / low confidence / loop) can be demonstrated or explained.
- **AC2:** On trigger, the twin pauses and requests input via the notch; otherwise it proceeds autonomously.

### FR-8 [P0] Live PiP feed
**As** the user, **I want** to watch the twin work, **so that** I trust what it's doing.
- **AC1:** The notch expands to show a live MJPEG feed of Profile B.
- **AC2:** Latency is low enough to see mouse movement and typing.

### FR-9 [P0] Jarvis voice output
**As** the user, **I want** spoken updates in a distinct assistant voice that uses my name, **so that** I can stay heads-down.
- **AC1:** Key events (nudge, clarification, completion) are spoken via ElevenLabs (preset Jarvis voice).
- **AC2:** The voice addresses the user by name.

### FR-10 [P0] BigQuery memory reveal
**As** a judge, **I want** to see that the twin's learning is real, **so that** the claim is credible.
- **AC1:** A live `SELECT * FROM agent_memory` shows the learned row(s), timestamped.
- **AC2:** Fallback: a pre-captured screenshot if the network fails.

### FR-11 [P1] Theatrical Fast-User-Switch reveal
**As** the presenter, **I want** to switch into Profile B live, **so that** the audience sees the twin's real desktop.
- **AC1:** Triggering FUS shows the macOS transition and lands in Profile B with the twin's work visible.

### FR-12 [P0] Web onboarding → persona file
**As** a new user, **I want** to set up my twin on the web, **so that** the product feels real and usable by anyone.
- **AC1:** The site presents landing → onboarding form → persona preview → download.
- **AC2:** Submitting the form generates the persona markdown file(s) in the agent's expected format/location (per-user home dir).
- **AC3:** Auth is stubbed; the download/install path is presented (not executed live).

---

## Section 6 — UI/UX Specifications

### 6.1 The notch interface (Profile A)

The notch UI is the product's face and the highest-leverage polish surface in a five-minute judging window — invest disproportionately here. Built in SwiftUI.

- **Resting state:** a slim pill hanging from the webcam notch, top-center, transparent/borderless, unobtrusive while the user works.
- **Nudge state:** drops/expands downward with a short message (sender + ask), spoken simultaneously by the Jarvis voice. Two affordances: approve / dismiss.
- **Expanded state:** reveals (a) the chat/voice input area and (b) the PiP feed of Profile B.
- **Input:** voice populates an editable text field; Enter sends. Typing is always available as a fallback.
- **Motion:** smooth, intentional transitions (the pill expanding under the notch). Every transition should feel crafted — this is where the reference project earned its strongest praise.

### 6.2 Visual language

- Dark, glassy, minimal; transparent background so it reads as part of the OS chrome.
- One distinct accent for the twin's "speaking/working" state (a subtle pulse), so the user can tell at a glance whether the twin is idle, working, or waiting on them.
- Three clear status indicators: **idle**, **working** (PiP active), **waiting for you** (escalation).

### 6.3 The onboarding website (thin but polished)

- **Landing:** one-line value prop, a short loop/gif of the twin working in the notch, a single primary CTA ("Create your Doppelgänger").
- **Onboarding form (multi-step):** name → role/context → writing style (tone, sign-off) → key contacts/projects → persona preview.
- **Preview:** show the generated persona summary ("Here's your twin") to make the form feel consequential.
- **Download:** present the installer and a 3-step setup graphic (the shown-not-shipped install story).

### 6.4 Accessibility / legibility for the demo

High contrast, large enough text to read on a projector, and audio that is intelligible over a room. Rehearse on the actual projector/audio if possible.

---

## Section 7 — API & Infrastructure Schematics (what data moves where)

### 7.1 Services & ports

| Port | Service | Session |
|---|---|---|
| 8420 | Orchestrator (brain, keys, tool routing, BigQuery, Gemini, MCP) | Profile A |
| 8421 | agent-server (MJPEG stream + action executor + Mail poll) | Profile B |
| 9222 | Browser CDP endpoint (browser-use) | Profile B |

### 7.2 Inter-profile message contract (build and freeze this FIRST)

> The reference team's loudest lesson was that integration seams between parallel workstreams cause the worst, latest failures. Agree this contract first and test the connection before either side is "done."

Orchestrator → agent-server (commands):
```json
{ "type": "action", "path": "computer_use|noop",
  "action": "click|type|key|read", "args": { } }
```
agent-server → Orchestrator (observations):
```json
{ "type": "observation", "screenshot_url": "http://localhost:8421/frame.jpg",
  "screen_state": "ok|modal|error", "result": { } }
```
Notch UI ↔ Orchestrator: chat/events over SSE or WebSocket; voice-in posts transcript text; voice-out receives text to synthesize.

Note: cloud-document writes (Docs/Sheets) are made by the **orchestrator** directly via MCP — they do NOT route through the agent-server, since they are API calls, not on-screen actions.

### 7.3 External calls

- **Gemini Computer Use** (orchestrator → Google): `{ user_goal, screenshot }` → `{ function_call: action }`.
- **BigQuery** (orchestrator → Google): write-through on each learned fact; `SELECT` for the reveal.
- **MCP connectors** (orchestrator → Google services): Google Doc write (notes), Google Sheet update (tracker), optional email/calendar.
- **ElevenLabs** (orchestrator → ElevenLabs): text → audio (Jarvis preset), played on Profile A speakers.

### 7.4 Secrets & environment

All keys (`GOOGLE_*`, `ELEVENLABS_API_KEY`, BigQuery credentials, MCP tokens) live in the orchestrator's `.env` on Profile A only — never in Profile B. **Agree env var names and API shapes on day one** (a named reference-project failure was divergent env/auth assumptions discovered at merge time).

### 7.5 Data-flow walkthrough (hero task)

1. AppleScript (B) detects unread mail → agent-server posts observation → orchestrator → notch nudge + Jarvis voice.
2. User approves (voice→text→Enter) → orchestrator plans first step.
3. Orchestrator routes web research to **browser-use** (B, :9222) → top 3 posts returned.
4. Ambiguity → orchestrator escalates via notch/voice → user answers → orchestrator **writes preference to BigQuery** and continues.
5. Orchestrator writes findings to a **Google Doc** and updates the **Google Sheet**, both via **MCP** (direct API calls, not through agent-server).
6. Orchestrator drives Mail (B) via Computer Use to compose the draft (persona from profile) → **stops at draft**.
7. Orchestrator → ElevenLabs → Jarvis summary on A's speakers.
8. Presenter runs BigQuery `SELECT` → learned row shown.
9. [P1] FUS → land in Profile B.

---

## Section 8 — Edge Cases, Failsafes & Out of Scope

### 8.1 Demo failure modes & failsafes

| Risk | Likelihood | Failsafe |
|---|---|---|
| Synthetic input fails in background session | Med-High | Do the permission runbook early; rehearse in the exact session state; keep Profile B foreground-capable as fallback |
| Screen Recording / Accessibility permission not granted | Med | Runbook before building features; smoke-test first |
| Web step hits cookie/login popup mid-demo | High | Escalation trigger #2 handles it; presenter nudges past it (supervised autonomy, framed as a feature) |
| Computer Use misclicks a small target | Med | Scope desktop actions to big targets/few steps; prefer MCP for document output; rehearse |
| MCP Doc/Sheet write fails or is unauthorized | Med | Authorize MCP connectors during setup; pre-create the target Doc/Sheet; fallback to a pre-filled doc screenshot |
| Network drops during BigQuery reveal | Low-Med | Read-local keeps agent running; pre-captured `SELECT` screenshot as fallback |
| Gemini latency stalls the loop | Med | Use Flash preview; pre-warm; narrate while it thinks |
| ElevenLabs call fails live | Low | Pre-render key audio clips as fallback |
| Live email accidentally sends | Low/High-impact | Hard stop at draft (FR-6); never wire auto-send for the demo |
| GCP free-tier quota throttles rehearsal | Med | Confirm credits applied to the project early |
| Voice mis-transcribes a command | Med | Edit-before-send guard (FR-2) |
| Integration-seam mismatch (UI ↔ orchestrator ↔ agent-server) | Med | Freeze the message contract (7.2) and env shapes (7.4) first; integration-test the seam early |

### 8.2 Build order (protects the demo under time pressure)

1. **[P0] GATE 0:** scaffold the repo (SwiftUI app + python orchestrator + python agent-server); create `.env.example` with every key name; write and FREEZE the inter-profile message contract (§7.2) as one shared schema both services import.
2. **[P0] Provision + permissions:** create Profile B; run the §4.7 permission runbook; smoke test (frames arrive, test click executes).
3. **[P0] Screen pipe + action executor:** MJPEG feed into the notch; execute a test click/type in B.
4. **[P0] Orchestrator + Gemini Computer Use loop:** screenshot → action → execute, for one desktop step.
5. **[P0] Notch UI:** nudge, voice-in (edit-then-Enter), PiP, voice-out (Jarvis).
6. **[P0] browser-use** for the Reddit step; **MCP** for the Google Doc + Sheet output.
7. **[P0] Escalation + BigQuery** write-through and `SELECT` reveal.
8. **[P0] Persona files** (hand-written/one-shot) consumed by the agent.
9. **[P1] Onboarding website:** landing → form → persona file → download story.
10. **[P1] FUS reveal**, polish, and **rehearse the full run ≥10×**.
11. **[P2] only if green:** subsequent-step "doesn't re-ask" payoff; extra polish.

Priority order is non-negotiable: **spine → demo rehearsal → onboarding polish.** If the site is half-done late, ship a simpler site; if the spine is half-done, there is no demo.

### 8.3 Out of scope (and the honest one-liner for each, if a judge asks)

- **Local shared folder (`/Users/Shared`)** — "Task output lives in your cloud documents (Docs/Sheets), which both you and the twin can reach — no fragile local sharing needed."
- **Real OAuth scraping persona pipeline** — "Persona is built from an onboarding questionnaire; full email/web ingestion is the production path."
- **Voice cloning of the user** — "The twin has its own assistant voice by design; it writes in your voice, speaks in its own."
- **Real authentication backend** — "Auth is stubbed for the demo; standard Auth0 in production."
- **Signed/notarized installer built live** — "The demo machine is provisioned; notarized distribution is a packaging step, not a product question."
- **Reinforcement-learning training loop (HEX / Prime Intellect)** — "Learning is a feedback-driven memory loop, not gradient RL — more reliable for an agent that must work on day one."
- **Cookie cloning** — "Not needed; the twin's apps are logged in directly in its profile."
- **Microsoft Teams/Outlook chat** — "Same pattern; email covers the demo. Teams is roadmap."
- **Multi-user / Windows / Linux** — "Single user, single Mac for now."

### 8.4 Definition of done (demo-ready)

- The full hero task runs end-to-end, unassisted except at the designed escalation, in under 5 minutes.
- Every P0 acceptance criterion passes.
- Every failsafe in 8.1 has been tested at least once.
- The full run has been rehearsed ≥10× on the actual demo machine, including audio on the actual room/projector where possible.
- A pre-captured fallback exists for each of: BigQuery reveal, Jarvis audio, the riskiest web step, and the MCP Doc/Sheet write.

---

## Appendix A — Locked decisions (provenance)

| Decision | Choice | Rationale |
|---|---|---|
| Inter-profile comms | localhost (no DigitalOcean) | Same machine; cloud relay adds latency + failure surface |
| Inter-profile task output | Google Doc + Sheet via MCP (no local shared folder) | Matches proven reference approach; cloud is the shared surface; one less local-FS failure mode |
| Memory store | BigQuery (not Snowflake) | One vendor (Google), free credits, demoable `SELECT`; aligns with Google-track target |
| Agent brain | Gemini Computer Use (`gemini-3-flash-preview`) | Purpose-built computer use; strongest on web; covered by GCP credits |
| Action paths | Computer use + browser-use + MCP | Must-haves; desktop flex + reliable web + reliable structured actions |
| Email auth | Mail.app login in Profile B + AppleScript poll | Real monitoring, zero OAuth, no cookie cloning |
| Persona | Onboarding form → markdown files in per-user home dir | Same agent input as a heavy pipeline, ~1% of the effort |
| Voice | ElevenLabs Jarvis preset, addresses user by name | No clone risk; warmer; separates written-as-you from spoken-as-itself |
| "Ask for help" fork | Knowledge gap ("which subreddit / client") | Sharper "didn't know → learned" story than a send confirmation |
| Learning | Feedback memory loop (write-through to BigQuery) | Honest, visible; NOT reinforcement learning |
| Notch UI stack | SwiftUI (native) | Native polish; matches reference; single-language front-end owner |
| Onboarding/distribution | Real thin site + stubbed auth + shown-not-shipped installer | Full product story; no notarization landmine |
| Reference repo | Reference only, build clean | Their repo is privately licensed; reference de-risks, forking disqualifies |
| Target | Google track + overall grand prize | Foreground Google stack; broad value prop |

*[USER_NAME] is a placeholder — set the actual name the Jarvis voice should use, or keep it configurable in onboarding.*
