# VNC Integration — Continuous View + Control of Profile B from Profile A

**Status:** de-risked and proven on-device (single Mac, two macOS users). This captures
the working recipe and the failsafe redesign needed to let the *agent* control Profile B
while you watch from Profile A.

Reference: the same approach is used by [23jmo/second-self](https://github.com/23jmo/second-self)
(Vine Server `:5901` + TigerVNC, SSH tunnel, LaunchAgents). We validated a no-extra-install
variant using macOS's built-in Screen Sharing through an SSH tunnel.

---

## 1. What this unlocks

The current MJPEG PiP can only show Profile B's **browser** (headless) or a failsafe
placeholder. It can **never** show B's native desktop, and desktop automation is **blocked**
whenever B is backgrounded. VNC removes both limits:

- **See** B's full native desktop from A, continuously, in a window.
- **Control** B (manually via VNC, and — with the failsafe change below — via the agent)
  while you stay in Profile A. No fast-user-switching.

---

## 2. The two blockers and the proven fixes

### Blocker 1 — "You cannot control your own screen"
macOS's Screen Sharing **client** refuses same-machine connections, even when you target a
different user (`vnc://clone@localhost` fails identically via loopback, LAN IP, and mDNS).

**Fix — SSH tunnel** (no extra software):
```bash
# Profile A: enable Remote Login (System Settings → General → Sharing → Remote Login)
ssh -NL 5901:localhost:5900 localhost      # forward local 5901 → Screen Sharing :5900 via an SSH hop
open vnc://localhost:5901                    # connect through the tunnel
# → choose "Log in as clone", enter clone's macOS credentials
```
The SSH hop makes the connection look non-local, so the self-screen check never fires.
Logging in **as a non-console user** (`clone`) yields that user's **virtual display** session.

**Alternative — Vine Server** (third-party VNC server on `:5901`): serves the session
directly with no self-check. `brew install --cask vine-server`, run it in clone's session.

### Blocker 2 — backgrounded session is black / not rendering
A fast-user-switched-away session can have its WindowServer suspended (nothing to capture
or render). **Fix:** keep a display attached to the background session — **BetterDisplay**
(virtual display) or a **dummy HDMI adapter**.

> On this machine the check `ps aux | grep -c "[W]indowServer"` returned **3** (both sessions
> active), so clone already renders and **no virtual display was needed**. Verify per-machine.

---

## 3. Ports & components

| Port | Service | Where |
| :--- | :--- | :--- |
| 5900 | macOS Screen Sharing (built-in VNC server) | system |
| 5901 | SSH-tunnel endpoint → 5900 (or Vine Server) | Profile A terminal |
| 8421 | agent-server (runs in clone's GUI session) | Profile B |
| 9222 | Chrome CDP | Profile B |
| 22 | Remote Login / SSH (for the tunnel) | system |

The repo runs agent-server/Chrome/Vine as **LaunchAgents** (`launchctl bootstrap gui/$UID …`)
so they live in clone's GUI session. We currently start agent-server manually in clone's
terminal, which is equivalent for testing.

---

## 4. ⚠️ The crux: pixel input hijacks the foreground — DO NOT bypass the failsafe

With clone's VNC session active, the agent-server still reports `active_console: false`
(the **physical** console is Profile A). We briefly added a `VNC_SUPERVISED_MODE` flag to
let `computer_use` run anyway, assuming "the agent runs in B's session, so it acts on B."

**That assumption is WRONG, and it caused a live hijack of Profile A.**

`pyautogui` posts input through the macOS **HID event tap** (`kCGHIDEventTap`), which
delivers events to the **active console session = the foreground = Profile A** — regardless
of which login session the process runs in. So the agent's clicks/keys landed in **A**, not B.
The original `is_profile_b_active_console()` gate was **correct**; bypassing it re-enabled
exactly the hijack it existed to prevent.

> **Both capture AND input target the foreground (verified).** `ImageGrab` /
> `CGWindowListCreateImage` from B's backgrounded session captures **Profile A's** screen
> (the main display), not B's — just like `pyautogui` input lands on A. So the MJPEG
> capture pipeline **cannot** show B's screen and must stay fail-closed (showing it would
> leak A). The **only** way to view B's actual session is the **VNC server**
> (`screensharingd` / Vine Server), which has the privilege to render and serve B's
> *virtual display* independent of the main display. Capture stays fail-closed; "see B"
> means the VNC channel, not screen-grab.

**Resolution:** `VNC_SUPERVISED_MODE` and `desktop_control_allowed()` were **removed**.
Pixel `computer_use` is permanently fail-closed (blocked unless B is the physical console).

### The session-correct toolkit (use these instead of background pixels)
To act on **B** from a background process without hijacking A, use mechanisms that run in
the **caller's** session, not the HID tap:

| Need | Tool | Why it's safe |
| :--- | :--- | :--- |
| Launch an app | **`open -a` (`open_app` action)** | LaunchServices launches in the caller's session (B) |
| Web | **Chrome CDP** (our `extract`/scrape) | DOM-level, no OS input events |
| In-app actions / menus | **AppleScript (`osascript`)** | Targets the app in B's session (needs Automation TCC) |
| Manual takeover | **VNC/RFB input** | `screensharingd` injects into B's session |
| Pixel control | **pyautogui** | ⚠️ HID tap → foreground; only when B IS the console |

True background *pixel* control would require posting via `kCGSessionEventTap` (the caller's
session) instead of the HID tap, or injecting through the RFB channel — not implemented.

---

## 5. Integration roadmap

1. **Reliable session-safe actions first** — `open_app` (done), plus AppleScript for in-app
   control. Avoid background pixels entirely.
2. **Embed the view in the notch app** — replace the MJPEG `PipView` with an inline VNC view:
   - fast path: **noVNC** in a `WKWebView` (+ `websockify` bridging 5901→WebSocket), or
   - native: a Swift RFB client (e.g. RoyalVNC) rendering into an `NSView`.
3. **Auto-start the plumbing** — script the SSH tunnel (or Vine Server) + the LaunchAgent
   pattern, so none of it is manual.

---

## 5b. TCC permissions need a one-time FOREGROUND grant

The session-safe lanes still require macOS privacy grants the first time:
- **Screen Recording** → for `/frame.jpg` capture of B
- **Accessibility** → for pyautogui (foreground only)
- **Automation** → for `osascript` to control each app (Notes, Safari, …)

**Critical gotcha:** TCC **consent dialogs can only be shown by the foreground console
session.** While B is backgrounded (you're in A, viewing via VNC), `tccd` cannot present
the prompt, so the call just fails — e.g. `osascript` returns `-1743 Not authorized to
send Apple events`, with **no prompt**, and `tccutil reset` doesn't help.

**Grant procedure (one-time, per app for Automation):**
1. Fast-user-switch **into** the agent user (foreground).
2. Trigger the action once (e.g. run the `osascript` one-liner in its Terminal) → approve
   the prompt that now appears.
3. Switch back. The grant **persists** and works while backgrounded thereafter.

So replicating this needs a brief foreground setup pass to grant all required TCC perms;
after that the agent runs fully backgrounded.

## 6. The session-safe action toolkit (proven end-to-end)

| Action | Mechanism | Hijack-safe? |
| :--- | :--- | :--- |
| Launch app | `open_app` → `open -a` | ✅ runs in B's session |
| In-app automation | `run_applescript` → `osascript` | ✅ Apple Events to B's apps (needs Automation TCC) |
| Web | Chrome CDP (`extract`/scrape) | ✅ DOM, no OS input |
| Gmail / Docs / Sheets / Calendar | MCP | ✅ API |
| View B from A | VNC (SSH tunnel) | ✅ read-only view + manual takeover |
| Pixel click/type | pyautogui | ⚠️ HID tap → foreground; **fail-closed**, foreground-only |

## 7. Verified on this machine (2026-05-30)

- ✅ SSH tunnel `5901→5900`, `open vnc://localhost:5901`, **"Log in as clone"** → clone's
  desktop visible in a window while staying in Profile A.
- ✅ Manual control via the VNC window.
- ✅ Two active WindowServers (rendering works without an added virtual display).
- ⛔ Agent control still blocked by `active_console:false` → motivates §4.
