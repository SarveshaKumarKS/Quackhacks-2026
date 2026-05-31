#!/usr/bin/env bash
set -euo pipefail

SECOND_USER="${SECOND_USER:-clone}"
SECOND_HOME="/Users/$SECOND_USER"
SECOND_REPO_DIR="${SECOND_REPO_DIR:-$SECOND_HOME/Quackhacks-2026}"
PRIMARY_REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_DIR="$SECOND_HOME/Library/LaunchAgents"
LOG_DIR="$SECOND_HOME/Library/Logs/DoppelgangerOS"
AGENT_PLIST="com.doppelganger.agent.plist"
CHROME_PLIST="com.doppelganger.chrome.plist"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "========================================="
echo " Doppelganger OS - Provisioning"
echo " Primary repo: $PRIMARY_REPO_DIR"
echo " Clone user:   $SECOND_USER"
echo " Clone repo:   $SECOND_REPO_DIR"
echo "========================================="

echo "[1/8] Checking clone user..."
if id "$SECOND_USER" >/dev/null 2>&1; then
  echo "User '$SECOND_USER' exists."
else
  echo "Creating user '$SECOND_USER'. macOS may prompt for an admin password."
  sudo sysadminctl -addUser "$SECOND_USER" -password -
fi

echo "[2/8] Preparing Profile B directories..."
sudo mkdir -p "$SECOND_REPO_DIR" "$LAUNCH_DIR" "$LOG_DIR"
sudo chown -R "$SECOND_USER:staff" "$SECOND_REPO_DIR" "$LAUNCH_DIR" "$LOG_DIR"

echo "[3/8] Syncing repo to Profile B..."
origin_url="$(cd "$PRIMARY_REPO_DIR" && git remote get-url origin 2>/dev/null || true)"
if sudo -u "$SECOND_USER" test -d "$SECOND_REPO_DIR/.git"; then
  sudo -H -u "$SECOND_USER" bash -lc "cd '$SECOND_REPO_DIR' && git pull --ff-only origin main" || true
elif [ -n "$origin_url" ]; then
  sudo rm -rf "$SECOND_REPO_DIR"
  if ! sudo -H -u "$SECOND_USER" git clone "$origin_url" "$SECOND_REPO_DIR"; then
    echo "Git clone failed; falling back to rsync from primary checkout."
    sudo mkdir -p "$SECOND_REPO_DIR"
    sudo rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.build' --exclude='*.pyc' --exclude='orchestrator/.env' "$PRIMARY_REPO_DIR/" "$SECOND_REPO_DIR/"
  fi
else
  sudo rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.build' --exclude='*.pyc' --exclude='orchestrator/.env' "$PRIMARY_REPO_DIR/" "$SECOND_REPO_DIR/"
fi
sudo chown -R "$SECOND_USER:staff" "$SECOND_REPO_DIR"

echo "[4/8] Installing Python dependencies for Profile B..."
sudo -H -u "$SECOND_USER" bash -lc "cd '$SECOND_REPO_DIR' && $PYTHON_BIN -m pip install --user -r agent-server/requirements.txt"

echo "[5/8] Initializing persona files for primary user and clone..."
"$PRIMARY_REPO_DIR/setup/init-persona.sh"
sudo -H -u "$SECOND_USER" bash -lc "DOPPELGANGER_HOME='$SECOND_HOME/.doppelganger' '$SECOND_REPO_DIR/setup/init-persona.sh'"

echo "[6/8] Installing LaunchAgents..."
sudo cp "$PRIMARY_REPO_DIR/setup/$AGENT_PLIST" "$LAUNCH_DIR/$AGENT_PLIST"
sudo cp "$PRIMARY_REPO_DIR/setup/$CHROME_PLIST" "$LAUNCH_DIR/$CHROME_PLIST"
sudo chown "$SECOND_USER:staff" "$LAUNCH_DIR/$AGENT_PLIST" "$LAUNCH_DIR/$CHROME_PLIST"

echo "[7/8] Starting Profile B services..."
"$PRIMARY_REPO_DIR/setup/restart-agent.sh" || {
  echo "LaunchAgent start failed. Make sure '$SECOND_USER' has an active GUI login session."
}

echo "[8/8] Manual macOS permission checklist:"
cat <<EOF

Switch into the '$SECOND_USER' macOS session once and grant:
  - Screen Recording for python3 / Terminal
  - Accessibility for python3 / Terminal
  - Automation prompts for apps you want AppleScript to control

To trigger Screen Recording while in Profile B:
  python3 -c "from PIL import ImageGrab; ImageGrab.grab(); print('screen capture attempted')"

To verify from Profile A:
  ./setup/smoke-test.sh

Optional VNC viewing:
  ./setup/start-vnc-tunnel.sh
  open vnc://localhost:5901
EOF
