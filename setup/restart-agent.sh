#!/usr/bin/env bash
set -euo pipefail

SECOND_USER="${SECOND_USER:-clone}"
SECOND_HOME="/Users/$SECOND_USER"
LAUNCH_DIR="$SECOND_HOME/Library/LaunchAgents"
LOG_DIR="$SECOND_HOME/Library/Logs/DoppelgangerOS"
AGENT_LABEL="com.doppelganger.agent"
CHROME_LABEL="com.doppelganger.chrome"

SECOND_UID="$(id -u "$SECOND_USER")"

echo "Restarting Doppelganger Profile B services for user '$SECOND_USER' (uid $SECOND_UID)..."
sudo mkdir -p "$LOG_DIR"
sudo chown -R "$SECOND_USER:staff" "$SECOND_HOME/Library/Logs"

sudo launchctl bootout "gui/$SECOND_UID/$AGENT_LABEL" 2>/dev/null || true
sudo launchctl bootout "gui/$SECOND_UID/$CHROME_LABEL" 2>/dev/null || true
sudo -u "$SECOND_USER" pkill -f 'agent-server/main.py' 2>/dev/null || true
sudo -u "$SECOND_USER" pkill -f 'remote-debugging-port=9222' 2>/dev/null || true

sleep 1

sudo launchctl bootstrap "gui/$SECOND_UID" "$LAUNCH_DIR/$CHROME_LABEL.plist"
sleep 2
sudo launchctl bootstrap "gui/$SECOND_UID" "$LAUNCH_DIR/$AGENT_LABEL.plist"

echo "Services requested. Verify with:"
echo "  ./setup/smoke-test.sh"
