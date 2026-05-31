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

## 4. The failsafe finding (the crux)

With clone's VNC virtual session active, the agent-server still reports:
```
active_console: false
```
because the **physical** console is still Profile A. So `is_profile_b_active_console()` —
which gates both `computer_use` and screen capture — keeps **blocking the agent**, even
though B is now fully visible and controllable.

**That gate is wrong for VNC mode.** Its original justification was:
1. backgrounded ⇒ not rendered (nothing to see/act on), and
2. acting could hijack the user's foreground (Profile A).

Under VNC + virtual display, **neither holds**: B renders to its own virtual display, and the
agent-server (running in B's session) only ever acts on **B's** session — never A's physical
screen.

### The redesign: an explicit, opt-in "VNC-supervised" mode
We do **not** silently loosen the guard. We add a deliberate operator flag:

```
VNC_SUPERVISED_MODE=true   # set when launching agent-server in Profile B
```

- `vnc_supervised()` — reads that flag (default **false** → fail-closed unchanged).
- `desktop_control_allowed()` = `is_profile_b_active_console()` **or** `vnc_supervised()`.
- `computer_use` block and screen capture now gate on `desktop_control_allowed()`.
- The agent-server `/` endpoint reports `control_allowed` (and `vnc_supervised`) alongside the
  truthful `active_console`.
- The orchestrator gates its "switch to Profile B" nudge on `control_allowed`, not raw
  `active_console` — so in VNC mode it proceeds with desktop control instead of nudging.

Safety properties preserved:
- Default (flag unset) = **identical fail-closed behavior**; a detection error still blocks.
- `active_console` is still reported truthfully (the flag is additive, not a lie).
- Enabling control is a conscious operator action that asserts "B has a live virtual display
  under VNC," accepting that capture/control target B's session.

---

## 5. Integration roadmap

1. **Failsafe change** *(this doc's §4 — implemented as a prototype)* — unlocks
   agent-controls-B-while-you-watch.
2. **Embed the view in the notch app** — replace the MJPEG `PipView` with an inline VNC view:
   - fast path: **noVNC** in a `WKWebView` (+ `websockify` bridging 5901→WebSocket), or
   - native: a Swift RFB client (e.g. RoyalVNC) rendering into an `NSView`.
3. **Auto-start the plumbing** — script the SSH tunnel (or Vine Server) + the LaunchAgent
   pattern, so none of it is manual.

---

## 6. Verified on this machine (2026-05-30)

- ✅ SSH tunnel `5901→5900`, `open vnc://localhost:5901`, **"Log in as clone"** → clone's
  desktop visible in a window while staying in Profile A.
- ✅ Manual control via the VNC window.
- ✅ Two active WindowServers (rendering works without an added virtual display).
- ⛔ Agent control still blocked by `active_console:false` → motivates §4.
