# Doppelganger OS Setup Commands

Run these from the primary profile unless noted otherwise.

```bash
./setup/provision.sh
```

Creates/verifies the `clone` user, syncs the repo to `/Users/clone/Quackhacks-2026`,
installs Profile B dependencies, initializes persona files, installs LaunchAgents,
and starts Chrome CDP plus agent-server in the clone GUI session.

```bash
./setup/restart-agent.sh
```

Restarts the Profile B LaunchAgents for Chrome CDP (`9222`) and agent-server (`8421`).

```bash
./setup/update-agent-server.sh
```

Pulls/syncs latest code into Profile B, reinstalls agent-server dependencies, and
restarts clone-side services.

```bash
./setup/smoke-test.sh
```

Checks orchestrator (`8420`), agent-server (`8421`), Chrome CDP (`9222`), frame
capture, and browser extraction through the agent-server.

```bash
./setup/init-persona.sh
```

Creates missing files under `~/.doppelganger/`:

- `identity.md`
- `preferences.md`
- `relationships.json`
- `episodic.md`

```bash
./setup/start-vnc-tunnel.sh
open vnc://localhost:5901
```

Starts the optional built-in Screen Sharing tunnel for viewing/manual control.
