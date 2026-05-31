# Quackhacks-2026

Doppelganger OS is a two-profile macOS agent. The primary user runs the SwiftUI
notch app and orchestrator on `127.0.0.1:8420`; the clone user runs the
agent-server on `127.0.0.1:8421` and Chrome CDP on `127.0.0.1:9222`.

## Demo-Ready Startup

Provision Profile B services once from the primary profile:

```bash
./setup/provision.sh
```

Restart the clone-side services after code changes or a reboot:

```bash
./setup/restart-agent.sh
```

Verify the running system:

```bash
./setup/smoke-test.sh
```

Launch the developer UI:

```bash
cd doppelganger-ui
swift run
```

Build a real app bundle for microphone and Speech Recognition permission testing:

```bash
cd doppelganger-ui
./build-app.sh
open .build/app/DoppelgangerOS.app
```

## Persona Files

Lightweight, manually editable persona files live outside the repo:

```text
~/.doppelganger/
|-- identity.md
|-- preferences.md
|-- relationships.json
`-- episodic.md
```

Create or refresh missing files with:

```bash
./setup/init-persona.sh
```

The orchestrator reads `identity.md` and `preferences.md` as prompt context when
drafting, summarizing, and deciding task behavior.

## Optional VNC Viewing

The in-app PiP still uses the MJPEG frame feed. For a fuller clone desktop view,
use the optional built-in Screen Sharing tunnel:

```bash
./setup/start-vnc-tunnel.sh
open vnc://localhost:5901
```

VNC is for viewing/manual takeover. PyAutoGUI pixel control remains fail-closed
unless Profile B is the active physical console.
